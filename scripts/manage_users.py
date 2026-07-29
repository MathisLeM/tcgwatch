"""Admin CLI to provision alpha accounts (public signup is closed).

Runs against whatever `DATABASE_URL` points at (local SQLite by default, or the
Supabase Postgres in prod when `.env` / the env var is set). Uses the same bcrypt
hashing as the API, so accounts created here log in normally.

Examples:
  python -m scripts.manage_users create ami@example.com            # random password (printed)
  python -m scripts.manage_users create moi@example.com --admin --password 'monMotDePasse'
  python -m scripts.manage_users list
  python -m scripts.manage_users passwd ami@example.com            # reset to a new random password
  python -m scripts.manage_users deactivate ami@example.com
  python -m scripts.manage_users delete ami@example.com

To provision an account on the PROD Supabase DB from your machine, run with the
prod connection string, e.g.:
  DATABASE_URL='postgresql://...supabase.co:5432/postgres' python -m scripts.manage_users create ...
"""
import argparse
import secrets
import string
import sys

import bcrypt

from api.database import SessionLocal, init_db
from api.models.user import User


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _random_password(n: int = 14) -> str:
    # Readable-enough random password (letters+digits), safe to paste/share once.
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _resolve_password(arg: str | None) -> tuple[str, bool]:
    """Return (password, was_generated). Enforces the 8-char minimum."""
    if arg:
        if len(arg) < 8:
            sys.exit("Le mot de passe doit faire au moins 8 caractères.")
        return arg, False
    return _random_password(), True


def cmd_create(args):
    password, generated = _resolve_password(args.password)
    with SessionLocal() as db:
        if db.query(User).filter(User.email == args.email).first():
            sys.exit(f"Un compte existe déjà pour {args.email}.")
        user = User(email=args.email, hashed_password=_hash(password), is_admin=args.admin)
        db.add(user)
        db.commit()
        db.refresh(user)
    role = "admin" if args.admin else "utilisateur"
    print(f"✅ Compte {role} créé : {args.email}  (id={user.id})")
    if generated:
        print(f"   Mot de passe : {password}")
        print("   ⚠️  Notez-le : il n'est pas récupérable (seul le hash est stocké).")


def cmd_list(args):
    with SessionLocal() as db:
        users = db.query(User).order_by(User.id).all()
    if not users:
        print("Aucun compte.")
        return
    print(f"{'id':>3}  {'email':<32} {'admin':<6} {'actif':<6} créé")
    for u in users:
        created = u.created_at.isoformat(timespec="minutes") if u.created_at else "?"
        print(f"{u.id:>3}  {u.email:<32} {str(u.is_admin):<6} {str(u.is_active):<6} {created}")


def cmd_passwd(args):
    password, generated = _resolve_password(args.password)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            sys.exit(f"Aucun compte pour {args.email}.")
        user.hashed_password = _hash(password)
        db.commit()
    print(f"✅ Mot de passe réinitialisé pour {args.email}.")
    if generated:
        print(f"   Nouveau mot de passe : {password}")


def _set_active(email: str, active: bool):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            sys.exit(f"Aucun compte pour {email}.")
        user.is_active = active
        db.commit()
    print(f"✅ Compte {email} {'activé' if active else 'désactivé'}.")


def cmd_delete(args):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            sys.exit(f"Aucun compte pour {args.email}.")
        db.delete(user)
        db.commit()
    print(f"🗑️  Compte supprimé : {args.email}")


def main():
    ap = argparse.ArgumentParser(description="Gestion des comptes TCGWatch (alpha).")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="Créer un compte")
    p.add_argument("email")
    p.add_argument("--password", help="Mot de passe (sinon généré et affiché)")
    p.add_argument("--admin", action="store_true", help="Compte admin")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("list", help="Lister les comptes")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("passwd", help="Réinitialiser un mot de passe")
    p.add_argument("email")
    p.add_argument("--password", help="Nouveau mot de passe (sinon généré et affiché)")
    p.set_defaults(func=cmd_passwd)

    p = sub.add_parser("activate", help="Réactiver un compte")
    p.add_argument("email")
    p.set_defaults(func=lambda a: _set_active(a.email, True))

    p = sub.add_parser("deactivate", help="Désactiver un compte")
    p.add_argument("email")
    p.set_defaults(func=lambda a: _set_active(a.email, False))

    p = sub.add_parser("delete", help="Supprimer un compte")
    p.add_argument("email")
    p.set_defaults(func=cmd_delete)

    args = ap.parse_args()
    # Ensure the schema exists (create_all on SQLite; Alembic already ran in prod).
    init_db()
    args.func(args)


if __name__ == "__main__":
    main()
