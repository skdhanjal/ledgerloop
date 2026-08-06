"""Investigator with a typed verdict instead of free text."""
from langchain.agents import create_agent

from graph.nodes import investigate_with_memory_factory

from .extraction import ExceptionVerdict
from .investigator import SYSTEM
from .middleware import ledgerloop_middleware

def investigate_node_factory_v3(model, tools):
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM,
        response_format=ExceptionVerdict,     # auto-wrapped by capability
        middleware=ledgerloop_middleware(model),
    )
   
    return investigate_with_memory_factory(agent)
