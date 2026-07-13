# Person-auth database migration

Back up the production database, then run the repository migration runner from `backend`:

```powershell
python scripts/apply_migrations.py
```

Migration `010_person_auth.sql` creates `users` and `project_members`, makes the legacy project password nullable, and permits the same display name under different users. Verify the migration by signing up a test user, completing OTP verification, and confirming that `GET /v2/projects` returns `My First Project`.

The existing project API keys remain valid for external integrations. Browser sessions use JWT plus `X-Project-Id`.
