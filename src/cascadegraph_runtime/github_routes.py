"""Cookie-only GitHub device sign-in endpoints."""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import github_access

router = APIRouter(prefix="/api/v1/github")


class GitHubAppInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(default="", max_length=110)
    slug: str = Field(default="", max_length=100)


def cookie(response, request, name, value, max_age):
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(name, value, max_age=max_age, httponly=True,
                        secure=secure, samesite="strict", path="/api")


@router.get("/status", operation_id="getGitHubStatus")
def status(request: Request):
    return github_access.status(request.cookies.get("cg_github", ""))


@router.post("/device", operation_id="startGitHubDevice")
async def start(request: Request, response: Response, data: GitHubAppInput | None = None):
    settings = data or GitHubAppInput()
    current = github_access.identity(request.cookies.get("cg_github", ""))
    if current and not settings.client_id and not settings.slug:
        settings = GitHubAppInput(client_id=current.client_id, slug=current.slug)
    handle, result = await github_access.start_device(request.cookies.get("cg_github_device", ""),
                                                     settings.client_id, settings.slug)
    cookie(response, request, "cg_github_device", handle, result["expires_in"])
    return result


@router.post("/device/poll", operation_id="pollGitHubDevice")
async def poll(request: Request, response: Response):
    handle, data = await github_access.poll_device(request.cookies.get("cg_github_device", ""))
    if handle:
        old_handle = request.cookies.get("cg_github", "")
        github_access.identities.pop(old_handle, None)
        cookie(response, request, "cg_github", handle, github_access.SESSION_TTL)
    if data["status"] != "pending":
        response.delete_cookie("cg_github_device", path="/api")
    return data


@router.delete("/connection", status_code=204, operation_id="disconnectGitHub")
def disconnect(request: Request):
    github_access.identities.pop(request.cookies.get("cg_github", ""), None)
    github_access.devices.pop(request.cookies.get("cg_github_device", ""), None)
    response = Response(status_code=204)
    for name in ("cg_github", "cg_github_device"):
        response.delete_cookie(name, path="/api")
    return response
