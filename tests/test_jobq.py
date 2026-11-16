import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "global/nomad/bin/py/jobq.py"
spec = importlib.util.spec_from_file_location("jobq", SCRIPT)
jq = importlib.util.module_from_spec(spec); spec.loader.exec_module(jq)
PY = '"%s"' % sys.executable


class JobQ(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = self._t.name
        self.addCleanup(self._cleanup)
        self.limit(1)  # 기존 테스트는 단일 진행 가정. 한도 2 동작은 self.limit(None) 테스트에서

    def limit(self, n):
        env = {"JOBQ_MAX": str(n)} if n else {}
        p = mock.patch.dict(os.environ, env)
        p.start()
        if not n:
            os.environ.pop("JOBQ_MAX", None)
        self.addCleanup(p.stop)

    def _cleanup(self):
        # 자동 기동 워커가 남아 있으면 끝날 때까지(워커 잠금이 풀릴 때까지) 잠깐 기다린 뒤 정리
        for _ in range(100):
            w = jq.FileLock(Path(self.dir, "content.worker.lock"))
            if w.try_acquire():
                w.release()
                break
            time.sleep(0.1)
        try:
            self._t.cleanup()
        except OSError:
            pass

    def q(self, *args):
        args = list(args)
        argv = [args[0], "--dir", self.dir] + args[1:]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                rc = jq.main(argv)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
                buf.write(str(e.code))
        return rc, buf.getvalue()

    def jobs(self, queue="content"):
        return json.loads((Path(self.dir) / (queue + ".json")).read_text(encoding="utf-8"))["jobs"]

    def statuses(self):
        return [j["status"] for j in self.jobs()]

    def wait_for(self, pred, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if pred():
                    return True
            except OSError:
                pass
            time.sleep(0.1)
        return False

    def test_add_starts_immediately_then_waits(self):
        rc, out = self.q("add", "video", "A")
        self.assertEqual(rc, 0); self.assertIn("바로 시작 #1", out)
        rc, out = self.q("add", "video", "B")
        self.assertEqual(rc, 0); self.assertIn("대기 #2", out); self.assertIn("순번 1", out)
        self.assertIn("순번 2", self.q("add", "video", "C")[1])
        self.assertEqual(self.statuses(), ["진행", "대기", "대기"])

    def test_done_auto_advances(self):
        self.q("add", "video", "A")
        self.q("add", "video", "B")
        rc, out = self.q("done", "1", "--result", "ok")
        self.assertEqual(rc, 0); self.assertIn("다음 작업 시작 #2 video B", out)
        self.assertEqual(self.statuses(), ["완료", "진행"])
        rc, out = self.q("fail", "2", "--error", "x", "--json")
        self.assertIn("큐 비어 있음", out)
        self.assertEqual(self.statuses(), ["완료", "실패"])

    def test_done_json_and_next_busy(self):
        for t in "ABC":
            self.q("add", "video", t)
        rc, out = self.q("next")
        self.assertEqual(rc, 3); self.assertIn("진행 중 #1 — 대기", out)
        rc, out = self.q("done", "1", "--json")
        self.assertEqual(json.loads(out.splitlines()[-1])["title"], "B")
        self.assertEqual(self.q("next")[0], 3)  # B 진행 중 → 두 번째 next는 대기
        self.q("done", "2"); self.q("done", "3")
        self.assertEqual(self.q("next")[0], 2)

    def test_different_kinds_share_one_queue(self):
        self.q("add", "video", "V")
        self.assertIn("대기 #2", self.q("add", "blog", "B")[1])
        rc, out = self.q("next")
        self.assertEqual(rc, 3); self.assertIn("진행 중 #1 — 대기", out)
        self.assertEqual([j["kind"] for j in self.jobs()], ["video", "blog"])
        self.assertEqual(self.statuses(), ["진행", "대기"])

    def test_cancel_and_reset(self):
        self.q("add", "blog", "A")
        self.q("add", "blog", "B")
        self.assertEqual(self.q("cancel", "2")[0], 0)
        self.assertEqual(self.statuses(), ["진행", "취소"])
        self.assertNotEqual(self.q("cancel", "1")[0], 0)  # 진행은 취소 불가
        self.assertEqual(self.q("reset", "1")[0], 0)
        self.assertEqual(self.statuses()[0], "대기")
        self.assertIn("A", self.q("list")[1])
        self.assertNotIn("B", self.q("list")[1])
        self.assertIn("B", self.q("list", "--all")[1])

    def test_run_success_and_failure(self):
        a = ("--no-autorun", "--cmd")
        self.q("add", "video", "ok", *a, PY + ' -c "print(1)"')
        self.q("add", "video", "bad", *a, PY + ' -c "import sys; sys.exit(5)"')
        self.q("add", "video", "after", *a, PY + ' -c "pass"')
        rc, out = self.q("run")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.statuses(), ["완료", "실패", "완료"])
        self.assertIn("종료코드 5", self.jobs()[1]["error"])
        self.assertEqual((Path(self.dir) / "logs" / "1.log").read_text().strip(), "1")
        self.assertFalse((Path(self.dir) / "content.worker").exists())

    def test_autorun_runs_in_order(self):
        # 두 작업이 순서대로 끝나는지: 두 번째 명령은 첫 번째가 만든 파일을 요구한다
        mark = Path(self.dir) / "mark.txt"
        c1 = PY + ' -c "import time; time.sleep(0.5); open(r\'%s\',\'w\').write(\'1\')"' % mark
        c2 = PY + ' -c "import sys,os; sys.exit(0 if os.path.exists(r\'%s\') else 9)"' % mark
        self.assertIn("바로 시작", self.q("add", "video", "first", "--cmd", c1)[1])
        self.assertIn("대기 #2", self.q("add", "blog", "second", "--cmd", c2)[1])
        self.assertTrue(self.wait_for(lambda: self.statuses() == ["완료", "완료"]), self.statuses())

    def test_autorun_after_done_of_agent_job(self):
        # 에이전트 작업이 진행 중이고 명령 작업이 대기 → done 하면 명령 작업이 자동 실행
        self.q("add", "blog", "agent")
        self.q("add", "video", "cmd", "--cmd", PY + ' -c "pass"')
        time.sleep(0.5)
        self.assertEqual(self.statuses(), ["진행", "대기"])  # 에이전트 작업이 끝나기 전엔 실행 안 됨
        rc, out = self.q("done", "1")
        self.assertIn("다음 작업 시작 #2", out)
        self.assertTrue(self.wait_for(lambda: self.statuses() == ["완료", "완료"]), self.statuses())

    def test_concurrent_add_threads(self):
        n = 20
        errs = []

        def add(i):
            try:
                jq.main(["add", "--dir", self.dir, "video", "t%d" % i])
            except BaseException as e:  # noqa
                errs.append(e)
        with contextlib.redirect_stdout(io.StringIO()):
            ts = [threading.Thread(target=add, args=(i,)) for i in range(n)]
            [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(sorted(j["id"] for j in self.jobs()), list(range(1, n + 1)))
        self.assertEqual(self.statuses().count("진행"), 1)

    def test_concurrent_add_processes(self):
        env = dict(os.environ, PYTHONUTF8="1")
        ps = [subprocess.Popen([sys.executable, str(SCRIPT), "add", "--dir", self.dir, "video", "p%d" % i],
                               stdout=subprocess.DEVNULL, env=env) for i in range(2)]
        self.assertEqual([p.wait() for p in ps], [0, 0])
        self.assertEqual(sorted(j["id"] for j in self.jobs()), [1, 2])
        self.assertEqual(sorted(self.statuses()), ["대기", "진행"])

    # ---- 코드 리뷰 반영 회귀 테스트 ----
    def touch(self, mark):
        return PY + ''' -c "open(r'%s','a').write('x')"''' % mark

    def _cmd_job(self, cmd2=None, **kw):
        j = {"id": 1, "kind": "video", "title": "J", "cmd": None, "status": "진행",
             "created": "t", "updated": "t"}
        j.update(kw)
        Path(self.dir).mkdir(exist_ok=True)
        Path(self.dir, "content.json").write_text(
            json.dumps({"next_id": 3, "jobs": [j, {"id": 2, "kind": "blog", "title": "N", "cmd": cmd2 or PY + ' -c "pass"',
                                                   "status": "대기", "created": "t", "updated": "t"}]}),
            encoding="utf-8")

    def _spawn_child(self, jid):
        """죽은 워커가 남긴 자식 흉내: `_child`를 직접 띄운다."""
        return subprocess.Popen([sys.executable, str(SCRIPT), "_child", str(jid), "--dir", self.dir])

    def _lock_held(self, jid):
        lk = jq.FileLock(Path(self.dir, "run-%d.lock" % jid))
        if lk.try_acquire():
            lk.release()
            return False
        return True

    def test_recovery_waits_for_live_child_then_uses_exit_code(self):
        # 복구 시점에 자식이 실행 중이면(JOBQ_MAX=1) 다음 명령은 자식 종료 전에 시작하지 않는다
        ev, cmds = self._timed_cmds(2)
        self._cmd_job(cmd2=cmds[1], cmd=cmds[0], launching="t")
        child = self._spawn_child(1)
        self.assertTrue(self.wait_for(lambda: self._lock_held(1)))
        rc, out = self.q("run")
        self.assertEqual(rc, 0, out)
        child.wait()
        self.assertEqual(self.statuses(), ["완료", "완료"])
        self.assertEqual([l[0] for l in ev.read_text().splitlines()], list("sese"))  # s1 e1 s2 e2: 겹치지 않음

    def test_recovery_records_child_exit_code(self):
        self._cmd_job(cmd=PY + ' -c "import sys; sys.exit(5)"', launching="t")
        self._spawn_child(1).wait()
        self.assertEqual(self.q("run")[0], 0)
        j = self.jobs()
        self.assertEqual([x["status"] for x in j], ["실패", "완료"])
        self.assertIn("종료코드 5", j[0]["error"])

    def test_recovery_launching_without_child_fails_not_rerun(self):
        mark = Path(self.dir, "mark.txt")
        self._cmd_job(cmd=self.touch(mark), launching="t")  # 자식이 뜨기 전에 워커가 죽은 경우
        self.assertEqual(self.q("run")[0], 0)
        self.assertFalse(mark.exists())
        j = self.jobs()
        self.assertEqual([x["status"] for x in j], ["실패", "완료"])
        self.assertIn("워커 중단", j[0]["error"])

    def test_late_child_does_not_run_after_recovery(self):
        mark = Path(self.dir, "mark.txt")
        self._cmd_job(cmd=self.touch(mark), launching="t")
        self.q("run")  # 복구가 '워커 중단'으로 확정
        self._spawn_child(1).wait()  # 뒤늦게 뜬 자식
        self.assertFalse(mark.exists())

    @staticmethod
    def _pid_alive(pid):
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def test_killed_child_does_not_orphan_command_tree(self):
        # _child가 강제 종료돼도 run 잠금 수명 = 명령 트리 수명 (한도 초과 방지)
        pidfile = Path(self.dir, "grandchild.pid")
        slow = PY + ''' -c "import os,time;open(r'%s','w').write(str(os.getpid()));time.sleep(5)"''' % pidfile
        self._cmd_job(cmd=slow, launching="t")
        child = self._spawn_child(1)
        self.assertTrue(self.wait_for(lambda: pidfile.exists() and pidfile.read_text().strip()))
        gpid = int(pidfile.read_text())
        child.kill(); child.wait()
        if os.name == "nt":  # Job(KILL_ON_JOB_CLOSE): 손자 프로세스가 함께 소멸
            self.assertTrue(self.wait_for(lambda: not self._pid_alive(gpid), timeout=3))
        else:  # 잠금 fd를 손자가 쥐고 있으므로 손자가 살아 있는 동안 잠금 유지 → 다음 작업은 시작되지 않음
            self.assertTrue(self._pid_alive(gpid))
            self.assertTrue(self._lock_held(1))
            self.assertEqual(self.statuses(), ["진행", "대기"])
            self.assertTrue(self.wait_for(lambda: not self._pid_alive(gpid), timeout=10))
            self.assertTrue(self.wait_for(lambda: not self._lock_held(1), timeout=3))

    def test_crash_after_spawn_uses_child_result_no_rerun(self):
        # Popen(_child) 직후 워커가 죽어도 자식 결과(.exit)로 기록하고 재실행하지 않는다
        mark = Path(self.dir, "mark.txt")
        self.q("add", "video", "J", "--no-autorun", "--cmd", self.touch(mark))

        class Boom(BaseException):
            pass
        real = subprocess.Popen

        def popen(*a, **k):
            real(*a, **k)
            raise Boom()
        with mock.patch.object(subprocess, "Popen", popen):
            with self.assertRaises(Boom):
                self.q("run")
        j = self.jobs()[0]
        self.assertEqual(j["status"], "진행"); self.assertTrue(j.get("launching"))
        self.assertTrue(self.wait_for(lambda: Path(self.dir, "run-1.exit").exists()))
        self.assertEqual(self.q("run")[0], 0)
        self.assertEqual(self.statuses(), ["완료"])
        self.assertEqual(mark.read_text(), "x")  # 한 번만 실행됨

    def test_restart_without_launching_runs(self):
        mark = Path(self.dir, "mark.txt")
        self._cmd_job(cmd=self.touch(mark))
        self.assertEqual(self.q("run")[0], 0)
        self.assertEqual(mark.read_text(), "x")
        self.assertEqual(self.statuses(), ["완료", "완료"])

    def test_corrupt_state_backed_up_and_stops(self):
        # 4) 손상된 JSON은 빈 큐로 덮지 않고 백업 후 오류(exit 1)
        Path(self.dir).mkdir(exist_ok=True)
        f = Path(self.dir, "content.json")
        f.write_text("{broken", encoding="utf-8")
        for argv in (("add", "video", "A"), ("list",), ("next",)):
            rc, out = self.q(*argv)
            self.assertEqual(rc, 1, argv)
            self.assertIn("손상", out)
        self.assertEqual(f.read_text(encoding="utf-8"), "{broken")
        self.assertTrue(list(Path(self.dir).glob("content.json.corrupt-*")))

    def test_worker_exit_race_with_done(self):
        # 5) 워커가 '에이전트 작업 busy'로 종료하려는 순간 done이 명령 작업을 진행으로 올려도 누락 없이 실행
        self.q("add", "blog", "agent")
        self.q("add", "video", "cmd", "--no-autorun", "--cmd", PY + ' -c "pass"')
        orig, calls = jq.run_loop, []

        def fake(a, s, base):
            if not calls:
                calls.append(1)
                self.q("done", "1", "--no-autorun")  # 종료 직전 끼어든 done → #2 진행
                return 0
            return orig(a, s, base)
        jq.run_loop = fake
        try:
            self.assertEqual(self.q("run")[0], 0)
        finally:
            jq.run_loop = orig
        self.assertEqual(self.statuses(), ["완료", "완료"])

    # ---- 동시 진행 한도(기본 2, JOBQ_MAX) ----
    def test_default_limit_two(self):
        self.limit(None)
        self.assertIn("바로 시작 #1", self.q("add", "video", "A")[1])
        self.assertIn("바로 시작 #2", self.q("add", "blog", "B")[1])
        rc, out = self.q("add", "video", "C")
        self.assertEqual(rc, 0); self.assertIn("대기 #3", out); self.assertIn("순번 1", out)
        self.assertEqual(self.statuses(), ["진행", "진행", "대기"])
        rc, out = self.q("next")
        self.assertEqual(rc, 3); self.assertIn("진행 중 #1, #2 — 대기", out)
        rc, out = self.q("done", "1")
        self.assertIn("다음 작업 시작 #3 video C", out)
        self.assertEqual(self.statuses(), ["완료", "진행", "진행"])

    def test_done_fills_all_free_slots(self):
        self.limit(2)
        for t in "ABCD":
            self.q("add", "video", t)
        self.limit(3)  # 한도를 올린 뒤 done → 빈 슬롯 2개를 한 번에 채움
        rc, out = self.q("done", "1", "--json")
        self.assertEqual([json.loads(x)["id"] for x in out.splitlines()[1:]], [3, 4], out)
        self.assertEqual(self.statuses(), ["완료", "진행", "진행", "진행"])

    def test_limit_env_validation(self):
        for bad in ("0", "abc", "-1"):
            self.limit(bad)
            rc, out = self.q("add", "video", "A")
            self.assertEqual(rc, 1, bad); self.assertIn("JOBQ_MAX", out)

    def _timed_cmds(self, n):
        script = Path(self.dir, "timed.py")
        script.parent.mkdir(exist_ok=True)
        body = ["import sys,time", "f=open(sys.argv[1],'a')",
                "f.write('s %f' % time.time() + chr(10));f.flush();time.sleep(3)",  # 부하 시 두 번째 명령 기동 지연에도 겹침이 보이도록 여유
                "f.write('e %f' % time.time() + chr(10));f.close()"]
        script.write_text(chr(10).join(body))
        # 명령마다 파일을 따로 쓴다: Windows의 'a' 모드 덧붙이기는 프로세스 간 원자적이지 않아 동시 시작 기록이 덮일 수 있다
        files = [Path(self.dir, "events-%d.txt" % i) for i in range(n)]

        class Events:
            def read_text(self):
                lines = [l for f in files if f.exists() for l in f.read_text().splitlines()]
                return chr(10).join(sorted(lines, key=lambda l: float(l.split()[1])))
        return Events(), [PY + ' "%s" "%s"' % (script, f) for f in files]

    def test_cmd_jobs_run_at_most_two_in_parallel(self):
        self.limit(None)
        ev, cmds = self._timed_cmds(3)
        for i, c in enumerate(cmds):
            self.q("add", "video", "j%d" % i, "--no-autorun", "--cmd", c)
        self.assertEqual(self.statuses(), ["진행", "진행", "대기"])
        self.assertEqual(self.q("run")[0], 0)
        self.assertEqual(self.statuses(), ["완료", "완료", "완료"])
        events = sorted((float(l.split()[1]), 1 if l[0] == "s" else -1) for l in ev.read_text().splitlines())
        cur = peak = 0
        for _, d in events:
            cur += d; peak = max(peak, cur)
        self.assertEqual(peak, 2)  # 3건이 동시에 돌지 않고, 2건은 실제로 겹쳐 돈다

    def test_agent_job_takes_slot_cmd_keeps_running(self):
        self.limit(None)
        self.q("add", "blog", "agent")
        self.q("add", "video", "c1", "--no-autorun", "--cmd", PY + ' -c "pass"')
        self.q("add", "video", "c2", "--no-autorun", "--cmd", PY + ' -c "pass"')
        self.assertEqual(self.statuses(), ["진행", "진행", "대기"])
        self.assertEqual(self.q("run")[0], 0)  # 에이전트 작업이 진행 중이어도 남은 슬롯으로 계속 실행
        self.assertEqual(self.statuses(), ["진행", "완료", "완료"])

    # ---- 구조 단순화 재검증 반영 ----
    def _holder(self, lockfile):
        code = chr(10).join([
            "import importlib.util,sys,time",
            "sp=importlib.util.spec_from_file_location('jq',sys.argv[1]);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)",
            "w=m.FileLock(sys.argv[2]);print('1' if w.try_acquire() else '0',flush=True);time.sleep(60)"])
        p = subprocess.Popen([sys.executable, "-c", code, str(SCRIPT), str(lockfile)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (p.kill(), p.wait(), p.stdout.close()))
        self.assertEqual(p.stdout.readline().strip(), "1")
        return p

    def test_os_lock_released_when_holder_killed(self):
        # A) 워커 잠금: 다른 프로세스가 쥐고 있으면 거부, 죽으면 OS가 즉시 해제 → 바로 새 워커 획득
        wl = Path(self.dir, "content.worker.lock")
        p = self._holder(wl)
        rc, out = self.q("run")
        self.assertEqual(rc, 3); self.assertIn("이미 워커", out)
        p.kill(); p.wait()
        w = jq.FileLock(wl)
        self.assertTrue(self.wait_for(w.try_acquire, timeout=3))  # 커널이 핸들을 정리하는 짧은 순간만 허용
        w.release()
        self.assertEqual(self.q("run")[0], 0)

    def test_state_lock_released_when_holder_killed(self):
        p = self._holder(Path(self.dir, "content.json.lock"))
        p.kill(); p.wait()
        t0 = time.time()
        self.assertEqual(self.q("add", "video", "A")[0], 0)
        self.assertLess(time.time() - t0, 5)

    def test_done_fail_rejected_for_cmd_job(self):
        # C) 명령 작업의 done/fail은 거부(슬롯 조기 반환 → 한도 초과 방지)
        self.q("add", "video", "C", "--no-autorun", "--cmd", PY + ' -c "pass"')
        self.q("add", "blog", "B")
        for verb in ("done", "fail"):
            rc, out = self.q(verb, "1")
            self.assertEqual(rc, 2); self.assertIn("워커가 결과를 기록", out)
        self.assertEqual(self.statuses(), ["진행", "대기"])

    def test_cmd_not_stuck_behind_waiting_agent_job(self):
        # D) 에이전트 대기 작업 뒤의 명령 작업도 빈 슬롯이 있으면 워커가 건너뛰고 실행
        self.limit(2)
        mk = lambda i, st, cmd=None: {"id": i, "kind": "k", "title": "T%d" % i, "cmd": cmd, "status": st,
                                      "created": "t", "updated": "t"}
        Path(self.dir, "content.json").write_text(json.dumps({"next_id": 4, "jobs": [
            mk(1, "진행"), mk(2, "대기"), mk(3, "대기", PY + ' -c "pass"')]}), encoding="utf-8")
        self.assertEqual(self.q("run")[0], 0)
        self.assertEqual(self.statuses(), ["진행", "대기", "완료"])

    def test_queue_option_removed(self):
        for argv in (("add", "video", "A", "--queue", "other"), ("list", "--queue", "x"), ("run", "--queue", "x")):
            self.assertEqual(self.q(*argv)[0], 2, argv)
        self.assertFalse(Path(self.dir, "other.json").exists())


if __name__ == "__main__":
    unittest.main()
