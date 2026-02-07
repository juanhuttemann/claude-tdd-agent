from agents.planner import planner
from agents.test_writer import test_writer
from agents.implementer import implementer
from agents.reviewer import reviewer
from agents.reporter import reporter

AGENTS = {
    "planner": planner,
    "test_writer": test_writer,
    "implementer": implementer,
    "reviewer": reviewer,
    "reporter": reporter,
}
