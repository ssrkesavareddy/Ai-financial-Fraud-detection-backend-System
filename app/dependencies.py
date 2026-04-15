from fastapi import Depends, HTTPException
from app.security import get_current_user
from app.models import User

def get_user(user: User = Depends(get_current_user)):
    return user


def require_role(required_roles: list[str]):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(403, "Access denied")
        return user
    return role_checker