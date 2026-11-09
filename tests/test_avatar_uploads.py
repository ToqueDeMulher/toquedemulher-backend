from uuid import UUID

import pytest

from app.core.settings import settings
from tests.test_auth import client, clean_db, create_logged_user


def test_avatar_upload_uses_persistent_storage(monkeypatch, tmp_path):
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    expected_url = 'https://example.test/storage/avatars/user.png'

    async def store_avatar(**kwargs):
        assert isinstance(kwargs['user_id'], UUID)
        return expected_url

    monkeypatch.setattr('app.api.v1.endpoints.user.upload_avatar_to_supabase', store_avatar,
                        raising=False)
    monkeypatch.setattr('app.api.v1.endpoints.user.STATIC_DIR', tmp_path, raising=False)
    response = client.post('/api/v1/user/me/avatar', headers=headers,
                           files={'file': ('avatar.png', b'image-fixture', 'image/png')})
    assert response.status_code == 200
    assert response.json()['avatar_url'] == expected_url
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def mock_storage(monkeypatch):
    import httpx
    from app.services import service

    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://storage.example.test')
    monkeypatch.setattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', 'test-storage-key')
    requests = []

    def accept(request):
        requests.append(request)
        return httpx.Response(200, json={'Key': 'stored'})

    transport = httpx.MockTransport(accept)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, 'AsyncClient', lambda **kwargs:
                        original_client(transport=transport, **kwargs))
    return requests


def test_avatar_upload_writes_authenticated_storage_path(mock_storage):
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    user_id = client.get('/api/v1/user/me', headers=headers).json()['id']
    response = client.post('/api/v1/user/me/avatar', headers=headers,
                           files={'file': ('avatar.png', b'png-fixture', 'image/png')})
    assert response.status_code == 200
    assert len(mock_storage) == 1
    request = mock_storage[0]
    assert f'/avatars/{user_id}/' in request.url.path
    assert request.url.path.endswith('.png')
    assert request.headers['authorization'] == 'Bearer test-storage-key'
    assert request.content == b'png-fixture'
    assert response.json()['avatar_url'].startswith(
        'https://storage.example.test/storage/v1/object/public/')


@pytest.mark.parametrize('contents,expected_status', [(b'', 400), (b'12345', 413)])
def test_invalid_avatar_size_never_reaches_storage(mock_storage, monkeypatch, contents,
                                                 expected_status):
    monkeypatch.setattr(settings, 'PRODUCT_IMAGE_MAX_BYTES', 4)
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post('/api/v1/user/me/avatar', headers=headers,
                           files={'file': ('avatar.png', contents, 'image/png')})
    assert response.status_code == expected_status
    assert mock_storage == []
    assert client.get('/api/v1/user/me', headers=headers).json()['avatar_url'] is None


def test_avatar_storage_timeout_does_not_change_profile(monkeypatch):
    import httpx
    from app.services import service

    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://storage.example.test')
    monkeypatch.setattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', 'test-storage-key')

    def timeout(request):
        raise httpx.ReadTimeout('Storage request timed out', request=request)

    original_client = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, 'AsyncClient', lambda **kwargs:
        original_client(transport=httpx.MockTransport(timeout), **kwargs))
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post('/api/v1/user/me/avatar', headers=headers,
                           files={'file': ('avatar.png', b'png-fixture', 'image/png')})
    assert response.status_code == 503
    assert client.get('/api/v1/user/me', headers=headers).json()['avatar_url'] is None
