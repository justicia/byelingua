import os
from season_ingestion.credentials import check_required_credentials

def test_missing_readonly_key(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL','url'); monkeypatch.delenv('SUPABASE_READONLY_KEY',raising=False)
    assert check_required_credentials('dry-run')['missing'] == ['SUPABASE_READONLY_KEY']

def test_missing_writer_key(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL','url'); monkeypatch.delenv('SUPABASE_SECRET_KEY',raising=False)
    assert check_required_credentials('apply')['missing'] == ['SUPABASE_SECRET_KEY']

def test_notification_missing_recipient_does_not_expose_values(monkeypatch):
    for key in ('RESEND_API_KEY','INGESTION_NOTIFICATION_EMAIL','RESEND_FROM_EMAIL'): monkeypatch.delenv(key,raising=False)
    result=check_required_credentials('notification')
    assert result['configured'] is False and all('secret' not in value.lower() for value in result['missing'])

def test_all_credentials_present(monkeypatch):
    for mode, keys in {'dry-run':('SUPABASE_URL','SUPABASE_READONLY_KEY'),'notification':('RESEND_API_KEY','INGESTION_NOTIFICATION_EMAIL','RESEND_FROM_EMAIL'),'apply':('SUPABASE_URL','SUPABASE_SECRET_KEY')}.items():
        for key in keys: monkeypatch.setenv(key,'configured')
        assert check_required_credentials(mode)['configured'] is True
