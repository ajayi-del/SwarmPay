import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.ows_service import OWSService

async def test_lit():
    ows = OWSService()
    from_wallet = {"role": "coordinator", "id": "test_from"}
    to_wallet = {"id": "test_to", "role": "sub-agent"}
    sub_task = {"budget_allocated": 10.0, "status": "working", "task_id": "t1", "agent_id": "test_agent"}
    amount = 5.0
    reputation = 4.0

    print("Evaluaging amount=5.0, rep=4.0, alloc=10.0 (multiplier=0.85 -> cap=8.5)")
    resp = ows.evaluate_and_sign_lit_action(from_wallet, to_wallet, amount, sub_task, reputation)
    print(resp)

    print("\nEvaluaging amount=9.0, rep=4.0, alloc=10.0 (multiplier=0.85 -> cap=8.5) (EXPECT REP GATE BLOCK)")
    resp2 = ows.evaluate_and_sign_lit_action(from_wallet, to_wallet, 9.0, sub_task, reputation)
    print(resp2)

if __name__ == "__main__":
    asyncio.run(test_lit())
