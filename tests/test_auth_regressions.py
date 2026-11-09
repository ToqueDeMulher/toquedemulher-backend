from uuid import UUID

from sqlmodel import Session, select

from app.models.user import UserInDB
from tests.test_auth import client, engine, clean_db, create_logged_user


def test_access_token_keeps_original_identity_after_email_reuse():
    token = create_logged_user('original@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    original_id = client.get('/api/v1/user/me', headers=headers).json()['id']
    assert client.put('/api/v1/user/me/email', headers=headers,
                      json={'new_email': 'moved@example.com'}).status_code == 200
    replacement = create_logged_user('original@example.com')
    replacement_id = client.get('/api/v1/user/me', headers={
        'Authorization': f'Bearer {replacement}'}).json()['id']
    response = client.get('/api/v1/user/me', headers=headers)
    assert original_id != replacement_id
    assert response.status_code == 200
    assert response.json()['id'] == original_id


def test_password_change_revokes_existing_access_token():
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    response = client.put('/api/v1/user/me/password', headers=headers, json={
        'current_password': 'Senha@123', 'new_password': 'OutraSenha@123'})
    assert response.status_code == 200
    assert client.get('/api/v1/user/me', headers=headers).status_code == 401


def test_password_reset_token_cannot_be_used_twice():
    from app.services.password_reset_service import create_password_reset_token

    create_logged_user()
    with Session(engine) as session:
        user = session.exec(select(UserInDB)).one()
        token = create_password_reset_token(user.email, user_id=user.id,
                                             password_hash=user.hashed_password)
    payload = {'token': token, 'new_password': 'PrimeiraSenha@123'}
    assert client.post('/api/v1/user/reset-password', json=payload).status_code == 200
    response = client.post('/api/v1/user/reset-password', json={
        **payload, 'new_password': 'SegundaSenha@123'})
    assert response.status_code == 400


def test_new_email_requires_its_own_confirmation():
    token = create_logged_user()
    headers = {'Authorization': f'Bearer {token}'}
    with Session(engine) as session:
        from app.core.time import utc_now
        user = session.exec(select(UserInDB)).one()
        user.email_confirmed_at = utc_now()
        session.add(user)
        session.commit()
    assert client.put('/api/v1/user/me/email', headers=headers,
                      json={'new_email': 'unverified@example.com'}).status_code == 200
    assert client.get('/api/v1/user/me', headers=headers).json()['email_confirmed_at'] is None


def test_confirmation_link_cannot_confirm_another_account_after_email_reuse():
    from app.services.email_confirmation_service import create_email_confirmation_token

    token = create_logged_user('original@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    user_id = UUID(client.get('/api/v1/user/me', headers=headers).json()['id'])
    link = create_email_confirmation_token('original@example.com', user_id=user_id)
    client.put('/api/v1/user/me/email', headers=headers,
               json={'new_email': 'moved@example.com'})
    replacement = create_logged_user('original@example.com')
    response = client.post('/api/v1/user/confirm-email', json={'token': link})
    assert response.status_code == 400
    assert client.get('/api/v1/user/me', headers={
        'Authorization': f'Bearer {replacement}'}).json()['email_confirmed_at'] is None


def test_legacy_email_only_access_tokens_require_login_again():
    from app.services.loginService import LoginAndJWT

    create_logged_user()
    token = LoginAndJWT.create_access_token({'sub': 'maria@example.com'})
    assert client.get('/api/v1/user/me', headers={
        'Authorization': f'Bearer {token}'}).status_code == 401


def test_forgot_password_delivers_a_bound_token_and_revokes_old_session(monkeypatch):
    delivered = []
    monkeypatch.setattr('app.services.password_reset_service.send_password_reset_email',
                        lambda email, name, token: delivered.append(token) or True)
    token = create_logged_user()
    response = client.post('/api/v1/user/forgot-password', json={'email': 'maria@example.com'})
    assert response.status_code == 200
    assert len(delivered) == 1
    assert client.post('/api/v1/user/reset-password', json={
        'token': delivered[0], 'new_password': 'NovaSenha@123'}).status_code == 200
    assert client.get('/api/v1/user/me', headers={
        'Authorization': f'Bearer {token}'}).status_code == 401
    assert client.post('/api/v1/user/login', json={
        'email': 'maria@example.com', 'password': 'NovaSenha@123'}).status_code == 200


def test_resend_confirmation_does_not_disclose_accounts_and_binds_user_id(monkeypatch):
    from app.services.email_confirmation_service import create_email_confirmation_token

    delivered = []
    token = create_logged_user()
    monkeypatch.setattr('app.api.v1.endpoints.user.send_confirmation_email',
                        lambda name, email, user_id: delivered.append((email, user_id)) or True)
    profile = client.get('/api/v1/user/me', headers={'Authorization': f'Bearer {token}'}).json()
    missing = client.post('/api/v1/user/resend-confirmation', json={'email': 'missing@example.com'})
    assert delivered == []
    pending = client.post('/api/v1/user/resend-confirmation', json={'email': 'maria@example.com'})
    assert pending.status_code == missing.status_code == 200
    assert pending.json() == missing.json()
    assert delivered == [('maria@example.com', UUID(profile['id']))]
    confirmation = create_email_confirmation_token('maria@example.com', user_id=UUID(profile['id']))
    assert client.post('/api/v1/user/confirm-email', json={'token': confirmation}).status_code == 200
    client.post('/api/v1/user/resend-confirmation', json={'email': 'maria@example.com'})
    assert len(delivered) == 1
