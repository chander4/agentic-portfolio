"""Dynamic Context Budget Assembler — pack segments under a hard token budget."""

from context_budget_assembler.assembler import ContextBudgetAssembler
from context_budget_assembler.models import AssembledContext, Segment

__all__ = ["AssembledContext", "ContextBudgetAssembler", "Segment"]
__version__ = "0.1.0"
