from fastapi import Depends, HTTPException, status


def get_current_user(token: str = "fake-token"):
    # placeholder security dependency; replace with real auth
    if token != "fake-token":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return {"user_id": "system"}
