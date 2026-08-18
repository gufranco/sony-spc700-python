"""Which parts this package covers, and what each one is.

The SPC700 is unusual among the processors in a SNES in having essentially one
form. Sony built it into the S-SMP and it was never sold on its own, so there is
no family of pin variants or licensee revisions to model the way the 65xx parts
demand. The catalogue exists anyway, and for the same reason it exists there: a
model is where hardware differences belong, and discovering one later should mean
adding an entry rather than restructuring the package around it.

Adding a model means adding an entry here and holding it to a conformance suite.
A model with no suite behind it does not belong in this table, because then its
fidelity would be a claim rather than a measurement.
"""


class UnknownModelError(Exception):
    pass


class Model:
    """One part: what it is, what it reaches, and how to build it."""

    def __init__(self, name, summary, address_bits, data_bits, core, aliases=()):
        self.name = name
        self.summary = summary
        self.address_bits = address_bits
        self.data_bits = data_bits
        self.core = core
        self.aliases = tuple(aliases)

    @property
    def address_mask(self):
        return (1 << self.address_bits) - 1

    def build(self, memory, **options):
        return self.core(self, memory, **options)

    def __repr__(self):
        return f"<Model {self.name}, {self.address_bits} address bits>"


def _build_spc700(model, memory, **options):
    from .core import Cpu as Spc700

    cpu = Spc700(memory, **options)
    cpu.model = model.name
    return cpu


_CATALOGUE = (
    Model(
        name="spc700",
        summary=(
            "Sony SPC700, the eight bit core inside the S-SMP that drives the SNES "
            "audio unit. Sixteen address lines over a flat sixty four kilobyte space, "
            "an instruction set shaped like a 6502 with a sixteen bit register pair "
            "bolted across the accumulator and the Y register."
        ),
        address_bits=16,
        data_bits=8,
        core=_build_spc700,
        aliases=("spc", "ssmp", "smp", "sonyspc700"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name):
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name):
    """The model of that name, however it happens to be written."""
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this package covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
