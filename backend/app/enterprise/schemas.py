from pydantic import BaseModel


class EnterpriseStubResponse(BaseModel):
    message: str
    feature: str
