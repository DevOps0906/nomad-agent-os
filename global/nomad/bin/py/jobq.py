#!/usr/bin/env python3
"""jobq — 연속 제작 작업 큐(영상 생성·블로그 포스팅). 큐 하나에서 동시 진행 최대 JOBQ_MAX(기본 2)건, 나머지는 대기. 표준 라이브러리만."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

WAIT, RUN, DONE, FAIL, CANCEL = "대기", "진행", "완료", "실패", "취소"
DEFAULT_MAX = 2  # 동시 진행 기본 한도(JOBQ_MAX로 조정)
QUEUE = "content"  # 큐는 종류와 무관하게 항상 하나 (종류는 표시용)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileLock:
    """OS 파일 잠금(Windows msvcrt.locking · POSIX flock). 프로세스가 죽으면 OS가 자동 해제한다."""

    def __init__(self, path):
        self.path = str(path)
        self.f = None

    def try_acquire(self):
        f = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self.f = f
        return True

    def release(self):
        f, self.f = self.f, None
        if f is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        f.close()  # POSIX flock도 닫으면 해제


class Store:
    def __init__(self, base):
        self.base = Path(base)
        self.path = self.base / (QUEUE + ".json")
        self.lockpath = self.base / (QUEUE + ".json.lock")

    def load(self):
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"next_id": 1, "jobs": []}
        try:
            d = json.loads(raw)
            if not (isinstance(d, dict) and isinstance(d.get("jobs"), list) and isinstance(d.get("next_id"), int)):
                raise ValueError("형식")
            return d
        except ValueError:
            bak = self.path.with_name("%s.corrupt-%s" % (self.path.name, datetime.now().strftime("%Y%m%d-%H%M%S")))
            bak.write_text(raw, encoding="utf-8")
            raise SystemExit("상태 파일이 손상되었습니다: %s (백업 %s) — 확인 후 직접 복구하세요" % (self.path, bak))

    def save(self, data):
        tmp = self.path.with_suffix(".tmp%d" % os.getpid())
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def __enter__(self):
        self.base.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.lockpath)
        t0 = time.time()
        while not self.lock.try_acquire():
            if time.time() - t0 > 20:
                raise SystemExit("잠금을 얻지 못했습니다: %s" % self.lockpath)
            time.sleep(0.01)
        return self

    def __exit__(self, *a):
        self.lock.release()


def find_job(d, jid):
    j = next((x for x in d["jobs"] if x["id"] == jid), None)
    if j is None:
        raise SystemExit("작업 #%d 를 찾지 못했습니다" % jid)
    return j


def mutate(args, jid, fn):
    s = Store(args.dir)
    with s:
        d = s.load()
        fn(find_job(d, jid))
        s.save(d)


def limit():
    """동시 '진행' 한도. 기본 2, 환경변수 JOBQ_MAX(1 이상 정수)로만 조정."""
    raw = os.environ.get("JOBQ_MAX")
    if raw is None or raw == "":
        return DEFAULT_MAX
    try:
        n = int(raw)
    except ValueError:
        n = 0
    if n < 1:
        raise SystemExit("JOBQ_MAX 는 1 이상의 정수여야 합니다: %r" % raw)
    return n


def running(d):
    return [j for j in d["jobs"] if j["status"] == RUN]


def wait_pos(d, job):
    w = [j["id"] for j in d["jobs"] if j["status"] == WAIT]
    return w.index(job["id"]) + 1 if job["id"] in w else None


def fill(s, only_cmd=False, max_n=None):
    """잠금 안에서 호출. 빈 슬롯만큼 대기 작업을 오래된 순서로 '진행'으로 올린다. only_cmd면 대기 중
    명령 작업만 순서대로 골라 올린다(에이전트 작업은 건너뜀 — add/next/done이 승격). → (시작된 작업 목록, 상태)"""
    d = s.load()
    lim, started = limit(), []
    while len(running(d)) < lim and (max_n is None or len(started) < max_n):
        w = next((j for j in d["jobs"] if j["status"] == WAIT and (j.get("cmd") or not only_cmd)), None)
        if w is None:
            break
        w["status"], w["updated"] = RUN, now()
        started.append(w)
    if started:
        s.save(d)
    return started, d


def ids(jobs):
    return ", ".join("#%d" % j["id"] for j in jobs)


def spawn_worker(a):
    """run 워커를 분리(detached) 프로세스로 기동. 이미 워커가 있으면 새 워커가 잠금 실패로 곧바로 종료하고,
    기존 워커는 종료 직전 재검사하므로 누락이 없다."""
    cmd = [sys.executable, os.path.abspath(__file__), "run", "--dir", a.dir]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=dict(os.environ, PYTHONUTF8="1"), **detached_kwargs())


def cmd_add(a):
    s = Store(a.dir)
    with s:
        d = s.load()
        j = {"id": d["next_id"], "kind": a.kind, "title": a.title, "cmd": a.cmd, "status": WAIT,
             "created": now(), "updated": now()}
        d["next_id"] += 1
        d["jobs"].append(j)
        s.save(d)
        fill(s)  # 슬롯이 비어 있으면 가장 오래된 대기부터 시작(보통 방금 추가한 것)
        d = s.load()
        j = find_job(d, j["id"])
        pos, run = wait_pos(d, j), running(d)
    if j["status"] == RUN:
        print("바로 시작 #%d [%s] %s" % (j["id"], QUEUE, a.title))
    else:
        print("대기 #%d [%s] 순번 %d (진행 중 %s 이후 시작)" % (j["id"], QUEUE, pos or 0, ids(run)))
    if a.cmd and not a.no_autorun:
        spawn_worker(a)
    return 0


def cmd_list(a):
    rows = []
    d = Store(a.dir).load()
    for j in d["jobs"]:
        if not a.all and j["status"] in (DONE, FAIL, CANCEL):
            continue
        rows.append((str(j["id"]), j["kind"], j["title"], j["status"], str(wait_pos(d, j) or "-"), j["updated"]))
    if not rows:
        print("작업 없음")
        return 0
    for r in [("id", "종류", "제목", "상태", "순번", "시각")] + rows:
        print(" | ".join(r))
    return 0


def cmd_next(a):
    s = Store(a.dir)
    with s:
        started, d = fill(s, max_n=1)
    if not started:
        run = running(d)
        if run:
            print("진행 중 %s — 대기" % ids(run))
            return 3
        print("대기 작업 없음")
        return 2
    j = started[0]
    print(json.dumps(j, ensure_ascii=False) if a.json else "진행 #%d [%s] %s" % (j["id"], j["kind"], j["title"]))
    return 0


def finish(a, status, key, text):
    s = Store(a.dir)
    with s:
        d = s.load()
        j = find_job(d, a.id)
        if j["status"] != RUN:
            raise SystemExit("#%d 는 진행 중이 아닙니다(%s)" % (a.id, j["status"]))
        if j.get("cmd"):  # 슬롯 조기 반환(한도 초과)·중복 실행 방지: 명령 작업 결과는 워커만 기록
            print("명령 작업은 워커가 결과를 기록합니다 (#%d)" % a.id)
            return 2
        j["status"], j["updated"] = status, now()
        if text:
            j[key] = text
        s.save(d)
        started, _ = fill(s)  # 끊김 없이: 빈 슬롯만큼 다음 대기 작업을 자동으로 진행으로
    print("%s #%d" % (status, a.id))
    for n in started:
        print(json.dumps(n, ensure_ascii=False) if a.json
              else "다음 작업 시작 #%d %s %s" % (n["id"], n["kind"], n["title"]))
    if not started:
        print("큐 비어 있음")
    if any(n.get("cmd") for n in started) and not a.no_autorun:
        spawn_worker(a)
    return 0


def cmd_cancel(a):
    def fn(j):
        if j["status"] != WAIT:
            raise SystemExit("대기 작업만 취소할 수 있습니다 (#%d: %s)" % (a.id, j["status"]))
        j["status"], j["updated"] = CANCEL, now()
    mutate(a, a.id, fn)
    print("취소 #%d" % a.id)
    return 0


def cmd_reset(a):
    def fn(j):
        if j["status"] != RUN:
            raise SystemExit("진행 중인 작업만 되돌릴 수 있습니다 (#%d: %s)" % (a.id, j["status"]))
        if j.get("cmd"):
            raise SystemExit("명령 작업은 워커가 관리합니다 (#%d)" % a.id)
        j["status"], j["updated"] = WAIT, now()
    mutate(a, a.id, fn)
    print("대기로 되돌림 #%d" % a.id)
    return 0


def worker_has_work(s):
    """워커가 처리할 일이 남았나: 진행 중인 명령 작업 또는 대기 중인 명령 작업."""
    return any(j["status"] in (RUN, WAIT) and j.get("cmd") for j in s.load()["jobs"])


def cmd_run(a):
    base = Path(a.dir)
    base.mkdir(parents=True, exist_ok=True)
    s = Store(a.dir)
    wlock = FileLock(base / (QUEUE + ".worker.lock"))
    while True:
        if not wlock.try_acquire():  # 워커 생존 내내 쥔다. 죽으면 OS가 해제
            print("이미 워커가 실행 중입니다")
            return 3
        try:
            rc = run_loop(a, s, base)
        finally:
            wlock.release()
        # 잠금을 놓은 뒤 한 번 더 확인: 그 사이 done/add가 명령 작업을 진행으로 올렸고
        # 새 워커는 우리 잠금 때문에 못 떴을 수 있다.
        if rc == 0 and worker_has_work(s):
            continue
        return rc


def finalize(s, jid, status, error=None):
    """워커가 명령 작업의 결과를 기록한다(명령 작업 종료 기록은 워커만)."""
    with s:
        d = s.load()
        x = find_job(d, jid)
        x["updated"] = now()
        x["status"] = status
        x.pop("launching", None)
        if error:
            x["error"] = error
        s.save(d)
    print("%s #%d" % (status, jid), flush=True)


def run_path(base, jid, ext):
    return Path(base) / ("run-%d.%s" % (jid, ext))


def exit_code(base, jid):
    try:
        return int(run_path(base, jid, "exit").read_text().strip())
    except (OSError, ValueError):
        return None


def record(s, base, jid, rc):
    """자식의 종료코드(.exit)대로 완료/실패를 기록. 코드를 알 수 없으면 '워커 중단'."""
    log = Path(base) / "logs" / ("%d.log" % jid)
    if rc is None:
        finalize(s, jid, FAIL, "워커 중단 (종료코드를 알 수 없음, 로그 %s)" % log)
    elif rc == 0:
        finalize(s, jid, DONE)
    else:
        finalize(s, jid, FAIL, "종료코드 %d (로그 %s)" % (rc, log))


def try_reap(s, base, jid):
    """죽은 워커가 남긴 작업. run 잠금을 얻으면 자식이 없다 → 잠금을 쥔 채 결과 기록(그 사이 늦게 뜬 _child는
    잠금을 못 얻거나 상태가 '진행'이 아니라 실행하지 않는다). 못 얻으면 자식이 실행 중 → False."""
    lk = FileLock(run_path(base, jid, "lock"))
    if not lk.try_acquire():
        return False
    try:
        record(s, base, jid, exit_code(base, jid))
    finally:
        lk.release()
    return True


def detached_kwargs(no_window=False):
    if os.name == "nt":  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS(워커) / CREATE_NO_WINDOW(자식: 명령 쉘이 창을 띄우지 않게)
        return {"creationflags": 0x00000200 | (0x08000000 if no_window else 0x00000008)}
    return {"start_new_session": True}


def launch(s, a, j):
    """작업에 launching을 먼저 저장한 뒤 `_child`를 띄운다. 명령 실행·로그·종료코드 기록은 _child가 run 잠금을 쥐고 한다."""
    with s:
        d = s.load()
        find_job(d, j["id"])["launching"] = now()
        s.save(d)
    print("실행 #%d %s" % (j["id"], j["title"]), flush=True)
    cmd = [sys.executable, os.path.abspath(__file__), "_child", str(j["id"]), "--dir", a.dir]
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=dict(os.environ, PYTHONUTF8="1"), **detached_kwargs(True))


_JOB = None  # Windows Job 핸들: 닫지 않고 프로세스 수명 동안 보유


def _bind_to_kill_job():
    """Windows: 자신을 KILL_ON_JOB_CLOSE Job에 넣는다. 이후 띄우는 명령 트리가 같은 Job에 속해,
    _child가 강제 종료되면(핸들이 닫히면) 명령 트리도 함께 죽는다. 실패하면 경고 후 기존 동작."""
    global _JOB
    import ctypes
    from ctypes import wintypes as w

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

    class EXT(ctypes.Structure):
        _fields_ = [("Basic", BASIC), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = w.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    k.GetCurrentProcess.restype = w.HANDLE
    h = k.CreateJobObjectW(None, None)
    info = EXT()
    info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not h or not k.SetInformationJobObject(h, 9, ctypes.byref(info), ctypes.sizeof(info))             or not k.AssignProcessToJobObject(h, k.GetCurrentProcess()):
        print("경고: Job 할당 실패(오류 %d) — _child가 강제 종료되면 명령이 남을 수 있습니다" % ctypes.get_last_error(),
              file=sys.stderr)
        return
    _JOB = h


def cmd_child(a):
    """명령 실행기. run 잠금의 수명을 명령 트리 수명에 묶는다: POSIX는 잠금 fd를 명령 트리에 물려주고(pass_fds),
    Windows는 KILL_ON_JOB_CLOSE Job으로 _child가 죽으면 트리도 죽게 한다.
    잔여 위험: POSIX에서 명령이 스스로 데몬화하며 fd를 닫는 경우, Windows에서 Job 할당이 실패한 경우."""
    base = Path(a.dir)
    lk = FileLock(run_path(base, a.id, "lock"))
    if not lk.try_acquire():  # 이미 실행 중이거나 복구가 쥐고 있음 → 아무것도 실행하지 않는다
        return 0
    try:
        s = Store(a.dir)
        with s:
            j = find_job(s.load(), a.id)
            cmd = j.get("cmd") if j["status"] == RUN else None
        if not cmd:
            return 0
        (base / "logs").mkdir(exist_ok=True)
        kw = {}
        if os.name == "nt":
            _bind_to_kill_job()
        else:
            kw["pass_fds"] = [lk.f.fileno()]
        with open(base / "logs" / ("%d.log" % a.id), "wb") as f:
            try:
                rc = subprocess.call(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, **kw)
            except OSError as e:
                f.write(str(e).encode("utf-8"))
                rc = -1
        tmp = run_path(base, a.id, "exit.tmp")
        tmp.write_text(str(rc))
        os.replace(tmp, run_path(base, a.id, "exit"))
    finally:
        lk.release()
    return 0


def run_loop(a, s, base):
    children, ran = {}, 0  # jid -> Popen(이 워커가 띄운 _child) | None(죽은 워커의 자식: run 잠금으로 생존 판단)
    while True:
        with s:
            fill(s, only_cmd=True)  # 빈 슬롯에 대기 명령 작업을 순서대로(에이전트 작업은 건너뜀)
            d = s.load()
            mine = [j for j in running(d) if j.get("cmd") and j["id"] not in children]
            waiting_cmd = any(j["status"] == WAIT and j.get("cmd") for j in d["jobs"])
        for j in mine:
            if j.get("launching"):  # 이전 워커가 띄웠을 수 있음 → 재실행하지 않고 run 잠금으로 판정
                if try_reap(s, base, j["id"]):
                    ran += 1
                else:
                    print("이전 워커의 #%d 가 아직 실행 중 — 종료를 기다립니다" % j["id"], flush=True)
                    children[j["id"]] = None
            else:
                children[j["id"]] = launch(s, a, j)
        if not children:
            if mine:
                continue
            if waiting_cmd:  # 에이전트 작업이 슬롯을 쥐고 있는 동안 대기 중인 명령 작업이 있으면 계속 기다린다
                time.sleep(0.5)
                continue
            if a.watch is None:
                print("대기 작업 없음 (실행 %d건)" % ran)
                return 0
            time.sleep(a.watch)
            continue
        time.sleep(0.2)
        for jid, proc in list(children.items()):
            if proc is None:
                if try_reap(s, base, jid):
                    del children[jid]
                    ran += 1
            elif proc.poll() is not None:
                # _child가 끝나도 명령 트리(POSIX: 상속된 잠금 fd)가 남아 있을 수 있다 → run 잠금으로 확인 후 기록
                if try_reap(s, base, jid):
                    del children[jid]
                    ran += 1
                else:
                    children[jid] = None


def build():
    p = argparse.ArgumentParser(prog="jobq", description="연속 제작 작업 큐")
    sub = p.add_subparsers(dest="c", required=True)

    def sp(name, fn):
        x = sub.add_parser(name)
        x.set_defaults(fn=fn)
        x.add_argument("--dir", help="저장소 (기본 <cwd>/.nomad/queue)")
        return x
    x = sp("add", cmd_add)
    x.add_argument("kind")
    x.add_argument("title")
    x.add_argument("--cmd")
    x.add_argument("--no-autorun", action="store_true", help="--cmd 작업의 워커 자동 기동 끄기")
    x = sp("list", cmd_list)
    x.add_argument("--all", action="store_true")
    x = sp("next", cmd_next)
    x.add_argument("--json", action="store_true")
    for name, status, key, opt in (("done", DONE, "result", "--result"), ("fail", FAIL, "error", "--error")):
        x = sp(name, lambda a, st=status, k=key, o=opt: finish(a, st, k, getattr(a, k)))
        x.add_argument("id", type=int)
        x.add_argument(opt)
        x.add_argument("--json", action="store_true")
        x.add_argument("--no-autorun", action="store_true")
    for name, fn in (("cancel", cmd_cancel), ("reset", cmd_reset)):
        x = sp(name, fn)
        x.add_argument("id", type=int)
    x = sp("_child", cmd_child)  # 내부용: 워커가 띄우는 명령 실행기
    x.add_argument("id", type=int)
    x = sp("run", cmd_run)
    x.add_argument("--watch", nargs="?", const=2.0, type=float, default=None, metavar="초")
    return p


def main(argv):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    a = build().parse_args(argv)
    if not a.dir:
        a.dir = os.path.join(os.getcwd(), ".nomad", "queue")
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
