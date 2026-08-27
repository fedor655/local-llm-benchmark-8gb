# Patch OpenHands runtime to load ONLY the AgentSkills plugin.
# Drops jupyter + vscode, whose synchronous init hangs the sandbox action-server
# on slow / network-replicated storage (the server never binds its port, the app
# gets "Connection reset by peer" on check_if_alive).
# Cost: no in-container Jupyter/IPython execution and no VS Code tab; the agent
# still works fully via bash + file editing (AgentSkills).
f = '/app/openhands/runtime/base.py'
s = open(f).read()
if 'PATCH_LIGHT_PLUGINS' not in s:
    out = []
    for ln in s.split('\n'):
        out.append(ln)
        if 'self.plugins.append(VSCodeRequirement())' in ln:
            out.append('        # PATCH_LIGHT_PLUGINS: keep only AgentSkills (jupyter/vscode hang on slow storage)')
            out.append('        self.plugins = [p for p in self.plugins if type(p).__name__ == "AgentSkillsRequirement"]')
    open(f, 'w').write('\n'.join(out))
print('patched:', 'PATCH_LIGHT_PLUGINS' in open(f).read())
