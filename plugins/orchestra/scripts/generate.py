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
        variants = {'default': matrix, **{name: values for name,values in matrix.get('presets', {}).items()
                                        if (values['model'],values['effort']) != (matrix['model'],matrix['effort'])}}
        for preset, values in variants.items():
            name = role['id'] if preset=='default' else role['id']+'-'+preset
            front = ['---', f'name: {name}', f"description: {json.dumps(role['description'])}",
                     f"model: {values['model']}", f"effort: {values['effort']}"]
            if role['id'] != 'orchestrator':
                front.append('disallowedTools: Agent')
            front += ['---', '', instructions.replace('__ORCHESTRA_ROOT__', '${CLAUDE_PLUGIN_ROOT}')]
            output[f'agents/{name}.md'] = '\n'.join(front) + '\n'
        if role['id'] == 'orchestrator':
            continue
        matrix = models['codex'][role['id']]
        variants = {'default': matrix, **{name: values for name,values in matrix.get('presets', {}).items()
                                        if (values['model'],values['effort']) != (matrix['model'],matrix['effort'])}}
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



def codex_package(root=ROOT, profiles=None):
    """Derive a legacy-native package without the unsupported portable root manifest."""
    profiles = generated(root) if profiles is None else profiles
    output = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root).as_posix()
        if not path.is_file() or path.is_symlink():
            continue
        if ('__pycache__' in path.parts or path.name == '.DS_Store' or
            relative == 'plugin.json' or relative.startswith(('agents/', '.claude-plugin/')) or
            relative in {'hooks/claude.json', 'hooks/mods.json', 'scripts/generate.py', 'tsconfig.json'} or
            relative.startswith(('hooks/mod/', 'types/'))):
            continue
        output[relative] = profiles[relative].encode() if relative in profiles else path.read_bytes()
    return output


def sync_codex_package(check, profiles):
    target = ROOT.parent / 'orchestra-codex'
    expected = codex_package(profiles=profiles)
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    stale = actual - set(expected)
    mismatch = {name for name, data in expected.items()
                if not (target/name).is_file() or (target/name).read_bytes() != data}
    if check and (stale or mismatch):
        raise ValueError('Native Codex package drift: ' + ', '.join(sorted(stale | mismatch)))
    if not check:
        for name in stale:
            (target/name).unlink()
        for name, data in expected.items():
            path = target/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return len(expected)


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
    package_count = sync_codex_package(args.check, expected)
    print(f'{package_count} Codex package files checked' if args.check else f'{package_count} Codex package files generated')
    print(f'{len(expected)} native profiles checked' if args.check else f'{len(expected)} native profiles generated')


if __name__ == '__main__':
    main()
