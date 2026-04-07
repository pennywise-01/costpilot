import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth.dependencies import get_current_user
from app.auth.models import User

# Override authentication dependency
def mock_get_current_user():
    user = User(
        id="test_user_id",
        email="test@example.com",
        display_name="Test User",
        hashed_password="hashed_password",
        is_active=True,
        verified=True
    )
    return user

app.dependency_overrides[get_current_user] = mock_get_current_user

async def run_test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/organizations/")
        print(f"Status Code GET: {response.status_code}")
        print(f"Response GET: {response.text}")
        
        response2 = await ac.post("/api/v1/organizations/", json={"name": "test", "currency": "USD"})
        print(f"Status Code POST: {response2.status_code}")
        print(f"Response POST: {response2.text}")

if __name__ == "__main__":
    asyncio.run(run_test())
