"""Dispatch distinct candidate permissions without relaxing historical grants."""

from . import annual_candidate as historical


def _module(authorization):
    from . import annual_runtime
    return annual_runtime if type(authorization) is annual_runtime.RuntimeAuthorization else historical


def authorization_fields(authorization):
    return _module(authorization).authorization_fields(authorization)


def validate_workflow_authorization(*, authorization, **kwargs):
    return _module(authorization).validate_workflow_authorization(authorization=authorization, **kwargs)


def write_run_binding(*, authorization, run_dir):
    return _module(authorization).write_run_binding(authorization=authorization, run_dir=run_dir)


def wrap_live_request(*, authorization, request):
    from . import annual_runtime
    if type(authorization) is annual_runtime.RuntimeAuthorization:
        return annual_runtime.wrap_live_request(authorization=authorization, request=request)
    return request
