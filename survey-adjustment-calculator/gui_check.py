"""Real Tk integration test, also callable inside the packaged executable."""
from pathlib import Path
import json
import tkinter as tk
import traceback

import numpy as np
from app import AdjustmentApp
from examples import EXAMPLES


def run(output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.stem + "-exports")
    work.mkdir(exist_ok=True)
    root = tk.Tk()
    callback_errors=[]
    root.report_callback_exception=lambda *args:callback_errors.append("".join(traceback.format_exception(*args)))
    root.withdraw()
    checks = {}
    try:
        app = AdjustmentApp(root)
        root.update()
        for model in EXAMPLES:
            app.switch_model(model)
            app.load_example(confirm=False)
            root.update()
            assert app.calculate(show_error=False), app.status.get()
            r = app.result
            assert len(app.observation_tree.get_children()) == r.n
            assert len(app.parameter_tree.get_children()) == r.t
            assert "计算报告" in app.report_text.get("1.0", "end")
            checks[model] = {"n":r.n, "t":r.t, "dof":r.dof, "v":r.v.tolist()}
            for fmt in ("csv", "txt", "json"):
                target = work / (model + "." + fmt)
                assert app.export_result(fmt, target)
                assert target.stat().st_size > 50
            doc = json.loads((work / (model + ".json")).read_text(encoding="utf-8"))
            assert doc["result"]["model"] == model
            assert len(doc["result"]["qvv"]) == r.n
            target = work / (model + ".sap.json")
            assert app.save_project(target)
            saved_v = r.v.copy()
            assert app.open_project(target)
            assert app.calculate(show_error=False)
            np.testing.assert_allclose(app.result.v, saved_v)
        # A changed text cell invalidates visible and exportable stale results.
        app.editors["l"].text.insert("end", "\n4")
        root.update()
        assert app.result is None
        assert not app.calculate(show_error=False)
        checks["invalid_input"] = app.status.get()
        # Switch away and back: the unsaved draft is retained verbatim.
        draft = app.editors["l"].get()
        app.switch_model("condition")
        root.update()
        app.switch_model("indirect_constraints")
        root.update()
        assert app.editors["l"].get() == draft
        checks["draft_retention"] = True
        from network_gui_check import check_network_ui
        checks["network_workspace"] = check_network_ui(app,work)
        root.update()
        assert not callback_errors, "\n".join(callback_errors)
        output.write_text(json.dumps({"ok":True,"checks":checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        output.write_text(json.dumps({"ok":False,"error":traceback.format_exc()}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    finally:
        root.destroy()


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "gui-check.json")
