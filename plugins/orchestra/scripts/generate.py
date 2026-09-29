#!/usr/bin/env python3
"""Generate native role profiles from the portable contracts."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generated(root=ROOT):
    roles = json.loads((root / 'config/roles.json').read_text())['roles']
    models = json.loads((root / 'config/models.json').read_text())
    output = {}
    for role in roles:
        instructions = role['prompt']
        for method in role['methods']:
            path = root / 'skills/orchestra' / method
            instructions += '\n\n' + path.read_text()
        instructions += '\n\nPlugin root: __ORCHESTRA_ROOT__. Read only the references relevant to your assignment. '
        instructions += 'Your launch brief must name mode, objective, ownership, prerequisites and acceptance checks.'
        matrix = models['claude'][role['id']]
        front = ['---', f"name: {role['id']}", f"description: {json.dumps(role['description'])}",
                 f"model: {matrix['model']}", f"effort: {matrix['effort']}"]
        if role['id'] != 'orchestrator':
            front.append('disallowedTools: Agent')
        front += ['---', '', instructions.replace('__ORCHESTRA_ROOT__', '${CLAUDE_PLUGIN_ROOT}')]
        output[f"agents/{role['id']}.md"] = '\n'.join(front) + '\n'
        if role['id'] == 'orchestrator':
            continue
        matrix = models['codex'][role['id']]
        variants = {'default': matrix, **matrix.get('presets', {})}
        for preset, values in variants.items():
            name = 'orchestra_' + role['id'].replace('-', '_')
            if preset != 'default':
                name += '_' + preset.replace('-', '_')
            prompt = instructions + f'\nNative preset: {preset}. Keep the selected model and effort fixed.'
            fields = {'name': name, 'description': role['description'] + f' ({preset})',
                      'model': values['model'], 'model_reasoning_effort': values['effort'],
                      'developer_instructions': prompt}
            body = '\n'.join(f'{k} = {json.dumps(v)}' for k, v in fields.items())
            body += '\n\n[agents]\nenabled = false\n'
            output[f'profiles/codex/{name}.toml'] = body
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = generated()
    actual = {str(p.relative_to(ROOT)) for directory, glob in [('agents', '*.md'), ('profiles/codex', '*.toml')]
              for p in (ROOT / directory).glob(glob)}
    stale = actual - set(expected)
    mismatches = [name for name, content in expected.items()
                  if not (ROOT / name).exists() or (ROOT / name).read_text() != content]
    if args.check:
        if stale or mismatches:
            parser.exit(1, 'Generated drift: ' + ', '.join(sorted(stale | set(mismatches))) + '\n')
    else:
        for name in stale:
            (ROOT / name).unlink()
        for name, content in expected.items():
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print(f'{len(expected)} native profiles checked' if args.check else f'{len(expected)} native profiles generated')


if __name__ == '__main__':
    main()
