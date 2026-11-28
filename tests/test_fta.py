from sethread import fta as FT

def tree():
    return {"name": "t", "top": "T", "events": {
        "T": {"type": "top", "gate": "OR", "children": ["G1", "C"]},
        "G1": {"type": "intermediate", "gate": "AND", "children": ["A", "B"]},
        "A": {"type": "basic", "q": 1e-2}, "B": {"type": "basic", "lambda_fit": 1000, "hours": 1000}, "C": {"type": "basic", "q": 1e-5}}}

def test_cut_sets_and_probability():
    a = FT.analyse(tree())
    assert sorted(map(tuple, (c for c, _ in a["cut_sets"]))) == [("A", "B"), ("C",)]
    assert abs(a["top_rare"] - (1e-2 * 1e-3 + 1e-5)) < 1e-12 and a["spof"] == ["C"]

def test_vote_absorption_and_ccf():
    t = {"name": "v", "top": "T", "events": {"T": {"type": "top", "gate": "AND", "children": ["G1", "G2"]},
         "G1": {"type": "intermediate", "gate": "OR", "children": ["A", "X"]}, "G2": {"type": "intermediate", "gate": "OR", "children": ["B", "X"]},
         "A": {"type": "basic", "q": .1}, "B": {"type": "basic", "q": .1}, "X": {"type": "basic", "q": .01}}}
    a = FT.analyse(t)
    assert ["X"] in [c for c, _ in a["cut_sets"]] and a["ccf"] == [("T", ["X"])]
    v = {"name": "k", "top": "T", "events": {"T": {"type": "top", "gate": "VOTE", "k": 2, "children": ["A", "B", "C"]}, **{x: {"type": "basic", "q": .1} for x in "ABC"}}}
    assert len(FT.analyse(v)["cut_sets"]) == 3 and "<svg" in FT.svg(v)

def test_validation():
    t = tree(); t["events"]["G1"]["children"].append("Z")
    assert any("Z" in e for e in FT.validate(t))
