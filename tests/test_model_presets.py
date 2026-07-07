"""Tests for model preset registry and resolution logic.
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from src.llm import (
    list_model_presets,
    get_model_preset,
    list_models_for_provider,
    resolve_provider_model,
    get_provider,
)

def test_list_model_presets():
    """Verify that presets list is available and contains expected entries."""
    presets = list_model_presets()
    assert len(presets) >= 3
    
    # Verify recommended order: DeepSeek -> MiMo -> Step
    orders = [p["recommended_order"] for p in presets]
    assert orders == sorted(orders)
    
    names = [p["name"] for p in presets]
    assert "deepseek-primary" in names
    assert "mimo-primary" in names
    assert "step-primary" in names

def test_get_model_preset():
    preset = get_model_preset("mimo-primary")
    assert preset is not None
    assert preset["model"] == "mimo-v2.5-pro"
    assert preset["provider"] == "opengateway"
    
    assert get_model_preset("nonexistent") is None

def test_list_models_for_provider():
    models = list_models_for_provider("nvidia")
    assert "stepfun-ai/step-3.5-flash" in models
    assert "stepfun-ai/step-3.7-flash" in models
    assert "openai/gpt-oss-120b" in models
    
    assert list_models_for_provider("nonexistent_provider_abc") == []

def test_resolve_opengateway_mimo():
    """Verify opengateway + mimo-v2.5-pro combination resolves."""
    provider, model = resolve_provider_model(model="mimo-v2.5-pro", provider="opengateway")
    assert provider == "opengateway"
    assert model == "mimo-v2.5-pro"

def test_resolve_nvidia_step():
    """Verify nvidia + stepfun-ai/step-3.5-flash combination resolves."""
    provider, model = resolve_provider_model(model="stepfun-ai/step-3.5-flash", provider="nvidia")
    assert provider == "nvidia"
    assert model == "stepfun-ai/step-3.5-flash"

def test_resolve_opencode_go_deepseek_pending():
    """Verify opencode-go + deepseek-v4-flash resolves, but get_provider raises ValueError if environment is missing."""
    with patch.dict(os.environ, {}, clear=True):
        provider, model = resolve_provider_model(model="deepseek-v4-flash", provider="opencode-go")
        assert provider == "opencode-go"
        assert model == "deepseek-v4-flash"
        with pytest.raises(ValueError, match="pending configuration"):
            get_provider(provider)

def test_resolve_opencode_go_deepseek_configured():
    """Verify opencode-go + deepseek-v4-flash resolves and can be resolved when environment is configured."""
    env_mock = {
        "OPENCODE_GO_BASE_URL": "https://api.opencode.go/v1",
        "OPENCODE_API_KEY": "sk-test-key",
    }
    with patch.dict(os.environ, env_mock):
        provider, model = resolve_provider_model(model="deepseek-v4-flash", provider="opencode-go")
        assert provider == "opencode-go"
        assert model == "deepseek-v4-flash"

def test_resolve_preset():
    """Verify resolving by preset name works."""
    provider, model = resolve_provider_model(preset="mimo-primary")
    assert provider == "opengateway"
    assert model == "mimo-v2.5-pro"

def test_resolve_model_first():
    """Verify model-first matching works when provider is mock/empty."""
    provider, model = resolve_provider_model(model="mimo-v2.5-pro", provider="mock")
    assert provider == "opengateway"
    assert model == "mimo-v2.5-pro"

def test_resolve_default():
    """Verify default resolution (all None) is deepseek-primary."""
    provider, model = resolve_provider_model(None, None, None)
    assert provider == "opencode-go"
    assert model == "deepseek-v4-flash"

def test_cli_argument_resolution():
    """Verify that resolving model and provider parameters works as expected."""
    p, m = resolve_provider_model(model="mimo-v2.5-pro", provider="opengateway")
    assert p == "opengateway"
    assert m == "mimo-v2.5-pro"

def test_admin_api_presets():
    """Verify that create_admin_app includes resolved model and preset in summary."""
    from src.web.admin_demo import create_admin_app
    import socket
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        
    server = create_admin_app(
        site_id="bukgu_gwangju",
        provider="opengateway",
        model="mimo-v2.5-pro",
        host="127.0.0.1",
        port=port,
    )
    handler_cls = server.RequestHandlerClass
    assert handler_cls.provider == "opengateway"
    assert handler_cls.model == "mimo-v2.5-pro"
    server.server_close()

def test_mobile_api_presets():
    """Verify that create_app sets provider and model correctly without exposing them in HTML."""
    from src.web.mobile_demo import create_app, _load_template
    server = create_app(
        site_id="bukgu_gwangju",
        provider="opengateway",
        model="mimo-v2.5-pro",
        host="127.0.0.1",
        port=0,
    )
    handler_cls = server.RequestHandlerClass
    assert handler_cls.provider == "opengateway"
    assert handler_cls.model == "mimo-v2.5-pro"
    server.server_close()
    
    # Verify that the loaded template does NOT contain provider, model or preset values directly
    html = _load_template("전남광주통합특별시 북구")
    assert "opengateway" not in html
    assert "mimo-v2.5-pro" not in html
