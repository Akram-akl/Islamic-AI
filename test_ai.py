"""اختبار النظام"""
import sys
sys.path.insert(0, '.')
import asyncio
from core.ai_service import generate_answer, get_available_provider

print("المزودات المتاحة:")
print(get_available_provider())
print()

async def test():
    result = await generate_answer("ما هي أركان الإسلام؟", [])
    provider = result["provider"]
    answer = result["answer"]
    cached = result.get("cached", False)
    print(f"المزود: {provider}")
    print(f"من الكاش: {cached}")
    print(f"الإجابة: {answer[:300]}")

asyncio.run(test())
