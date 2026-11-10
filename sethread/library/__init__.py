"""Engineering knowledge the agents consult: regulations by trigger, failure mechanisms by discipline, standard test methods.
Company libraries can be added under <project>/library/*.yaml and are merged over the built-ins."""
import os, yaml
HERE = os.path.dirname(__file__)
def load(name, project_root=None):
    data = yaml.safe_load(open(os.path.join(HERE, name + ".yaml")))
    if project_root and os.path.exists(os.path.join(project_root, "library", name + ".yaml")):
        extra = yaml.safe_load(open(os.path.join(project_root, "library", name + ".yaml"))) or {}
        if isinstance(data, list): data = data + list(extra)
        else:
            for k, v in extra.items(): data.setdefault(k, []).extend(v)
    return data
def regulations_for(triggers, markets=None, project_root=None):
    out = []
    for r in load("regulations", project_root):
        if set(r["trigger"]) & set(triggers):
            mk = r["market"] if isinstance(r["market"], list) else [r["market"]]
            if not markets or set(mk) & set(markets) or "global" in mk: out.append(r)
    return out
