"""Integration checks used by both source and frozen executable self-tests."""
from pathlib import Path
import json
from types import SimpleNamespace
import numpy as np

from adjustment import MODEL_NAMES
from network import FAMILIES,example_network


def check_network_ui(app,work):
    work=Path(work);work.mkdir(exist_ok=True)
    root=app.root;view=app.network
    app.notebook.select(view);root.update()
    checks={}
    for family in FAMILIES:
        view.restore(example_network(family),dirty=True);view.mode.set("布网设计");view.precision.set("先验")
        assert view.update_analysis(),view.notice.get()
        s=view.solution
        assert view.stat_vars["n"].get()==str(s.model.stats["n"])
        assert len(view.obs_tree.get_children())==len(view.net.observations)
        assert "点位" in view.precision_report() or "mH" in view.precision_report()
        for ext in ("txt","json","csv"):assert view.export_result(work/(family+"."+ext))
        target=work/(family+".net.json");assert view.save_project(target);assert view.open_project(target)
        assert view.update_analysis()
        checks[family]=view.compiled.stats
    # Real measurement path, including angular iterations.
    view.restore(example_network("边角网",True));view.mode.set("实测平差");view.precision.set("后验")
    assert view.update_analysis(),view.notice.get()
    assert view.solution.result.posterior_sigma>0
    view.matrix_choice.set("Qxx · 参数协因数");view.show_matrix()
    assert "Qxx" in view.matrix_text.get("1.0","end")
    assert view.export_matrix(work/"Qxx.csv")
    # Exercise canvas click creation and deletion instead of calling only model methods.
    view.restore(example_network("水准网"));view.mode.set("布网设计");view.precision.set("先验")
    view.set_tool("point");view.on_click(SimpleNamespace(x=40,y=90))
    assert "P1" in view.net.points
    view.set_tool("height")
    for point in ("A","P1"):
        x,y=view.screen(view.net.points[point]["X"],view.net.points[point]["Y"])
        view.on_click(SimpleNamespace(x=x,y=y))
    assert len(view.net.observations)==6
    assert view.update_analysis(),view.notice.get()
    assert view.compiled.stats["n"]==6
    view.selection=("point","P1");view.delete_selected()
    assert "P1" not in view.net.points
    view.undo();assert "P1" in view.net.points
    view.redo();assert "P1" not in view.net.points
    # Automatic extraction enters the existing solver with the actual model.
    for method in MODEL_NAMES:
        view.restore(example_network());view.net.method=method;view.method.set(MODEL_NAMES[method]);view.mode.set("布网设计")
        assert view.update_analysis()
        view.send_matrix();root.update()
        assert not app.network_active()
        assert app.calculate(show_error=False),app.status.get()
        app.notebook.select(view);root.update()
    view.restore(example_network("导线网",True));view.mode.set("实测平差");view.precision.set("先验")
    assert view.update_analysis()
    final_coordinates=np.array([view.solution.points[p][a] for p,a in view.compiled.keys])
    view.send_matrix();root.update();assert app.calculate(show_error=False)
    np.testing.assert_allclose(app.result.parameters,final_coordinates,atol=1e-8)
    app.notebook.select(view);root.update()
    view.restore(example_network());view.mode.set("布网设计");view.precision.set("先验")
    # Editing invalidates old precision, a missing datum cannot leave stale Qxx.
    for p in view.net.points.values():p["fixed"]=[]
    view.changed();assert view.solution is None
    assert not view.update_analysis()
    assert view.stat_vars["defect"].get()=="1"
    assert "Qxx · 参数协因数" not in view.matrices
    checks["canvas_edit_undo_extraction_datum"]=True
    return checks
