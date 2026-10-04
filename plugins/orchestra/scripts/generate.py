#!/usr/bin/env python3
"""Generate native role profiles from the portable contracts."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_frontmatter(text):
    """Return (frontmatter dict of raw values, body) for a SKILL.md style file."""
    if not text.startswith('---\n'):
        return {}, text
    head, _, body = text[4:].partition('\n---\n')
    fields = {}
    for line in head.split('\n'):
        key, sep, value = line.partition(':')
        if sep:
            fields[key.strip()] = value.strip()
    return fields, body.lstrip('\n')


def check_resolution(root, roles):
    """Refuse a role whose preload skills or mode files do not resolve; Claude skips unknown skill names silently."""
    skills = root / 'skills'
    for role in roles:
        for name in [role['skill']] + ([] if role['id'] == 'orchestrator' else ['orchestra-worker']):
            path = skills / name / 'SKILL.md'
            if not path.is_file():
                raise ValueError(f"{role['id']}: preload skill '{name}' does not resolve to skills/{name}/SKILL.md")
            fields, _ = split_frontmatter(path.read_text())
            if fields.get('name') != name:
                raise ValueError(f"{role['id']}: skills/{name}/SKILL.md frontmatter name is not '{name}'")
            if fields.get('disable-model-invocation', 'false').lower() == 'true':
                raise ValueError(f"{role['id']}: skill '{name}' sets disable-model-invocation, which blocks preload")
        if role['id'] == 'orchestrator':
            continue
        for mode in role['modes']:
            if not (skills / role['skill'] / 'references' / f'{mode}.md').is_file():
                raise ValueError(f"{role['id']}: mode '{mode}' has no skills/{role['skill']}/references/{mode}.md")


def selection_lines(values):
    if values.get('selection') == 'user':
        return []
    return [f"model: {values['model']}", f"effort: {values['effort']}"]


def variants_of(matrix, claude=False):
    if matrix.get('selection') == 'user':
        return {'default': matrix}
    default = (matrix['model'], matrix['effort'])
    return {'default': matrix, **{name: values for name, values in matrix.get('presets', {}).items()
                                  if (values['model'], values['effort']) != default
                                  and not (claude and values.get('dispatch') == 'override')}}


def generated(root=ROOT):
    roles = json.loads((root / 'config/roles.json').read_text())['roles']
    models = json.loads((root / 'config/models.json').read_text())
    check_resolution(root, roles)
    skills = root / 'skills'
    output = {}
    for role in roles:
        orchestrator = role['id'] == 'orchestrator'
        instructions = role['prompt']
        if orchestrator:
            for method in role['methods']:
                instructions += '\n\n' + (skills / method).read_text()
        else:
            instructions += ('\n\nPlugin root: __ORCHESTRA_ROOT__. Skills are under <root>/skills/ and the CLI is '
                             '<root>/scripts/orchestra.py. Your launch brief must carry a Mode: line, objective, '
                             'ownership, prerequisites and acceptance checks.')
        preload = [role['skill']] if orchestrator else ['orchestra-worker', role['skill']]
        for preset, values in variants_of(models['claude'][role['id']], claude=True).items():
            name = role['id'] if preset == 'default' else role['id'] + '-' + preset
            front = ['---', f'name: {name}', f"description: {json.dumps(role['description'])}",
                     *selection_lines(values), f"skills: [{', '.join(preload)}]"]
            if role.get('read_only'):
                front.append('disallowedTools: Agent, Edit, Write, NotebookEdit')
            elif not orchestrator:
                front.append('disallowedTools: Agent')
            front += ['---', '', instructions.replace('__ORCHESTRA_ROOT__', '${CLAUDE_PLUGIN_ROOT}')]
            output[f'agents/{name}.md'] = '\n'.join(front) + '\n'
        if orchestrator:
            continue
        codex_instructions = instructions
        for name in preload:
            codex_instructions += '\n\n' + split_frontmatter((skills / name / 'SKILL.md').read_text())[1].rstrip('\n')
        matrix = models['codex'][role['id']]
        for preset, values in variants_of(matrix).items():
            name = 'orchestra_' + role['id'].replace('-', '_')
            if preset != 'default':
                name += '_' + preset.replace('-', '_')
            prompt = codex_instructions + f'\nNative preset: {preset}. Keep the selected model and effort fixed.'
            fields = {'name': name, 'description': role['description'] + f' ({preset})',
                      'model': values['model'], 'model_reasoning_effort': values['effort']}
            if role.get('read_only'):
                fields['sandbox_mode'] = 'read-only'
            fields['developer_instructions'] = prompt
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
    try:
        expected = generated()
    except ValueError as error:
        parser.exit(1, 'Generate refused: ' + str(error) + '\n')
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
