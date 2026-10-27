"""Model constants shared by the engine and the hook adapter, kept here so the engine never imports the hooks."""

EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')  # Claude Code effort levels, lowest first
MODEL_FAMILIES = ('opus', 'sonnet', 'haiku', 'fable')
FAMILY_RANK = {'haiku': 1, 'sonnet': 2, 'opus': 3}  # A session runs a card inline when it ranks at or above the card
MODEL_FIT = ('stronger', 'exact')  # policy `model_fit`: `stronger` (default) or the 2.15.1 exact-family rule
