from __future__ import annotations

import hmac
import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

CATEGORIES = (
    "Frutas físicas",
    "Gamepasses",
    "Skins de frutas",
    "Frutas permanentes",
    "Outros",
)

PHYSICAL_CATALOG = (
    ("129930-dragonwest.png", "100,00"),
    ("481301-dragoneast.png", "90,00"),
    ("72523-kitsune.png", "25,00"),
    ("109777-yetifruit.png", "14,00"),
    ("988436-tigerfruit.png", "13,00"),
    ("580043-lightingfruit.png", "10,00"),
    ("589002-controlfruit.png", "15,00"),
    ("707763-darkfruit.png", "9,00"),
    ("778421-trexfruit.png", "8,00"),
    ("795619-doughfruit.png", "8,00"),
    ("887925-sandfruit.png", "6,00"),
    ("440709-portalfruit.png", "6,00"),
)

PERMANENT_CATALOG = (
    ("129930-dragonwest.png", "160,00"),
    ("899308-galaxyemperyeankitsune.png", "128,00"),
    ("589002-controlfruit.png", "138,00"),
    ("988436-tigerfruit.png", "95,00"),
    ("109777-yetifruit.png", "92,00"),
    ("975559-crimsonemperyeankitsune.png", "89,00"),
    ("580043-lightingfruit.png", "80,00"),
    ("228287-venomfruit.png", "75,00"),
    ("218104-shadowfruit.png", "77,00"),
    ("151221-emberwestdragon.png", "75,00"),
    ("604555-werewolf-fruit.png", "75,00"),
    ("481301-dragoneast.png", "75,00"),
    ("707763-darkfruit.png", "71,00"),
    ("864673-blizzardfruit.png", "72,00"),
    ("778421-trexfruit.png", "71,00"),
    ("722299-greenlighting.png", "67,00"),
    ("123059-sadnesspain.png", "64,00"),
    ("321647-celestialpain.png", "57,00"),
    ("806092-redlighting.png", "59,00"),
    ("5544-frustrationpain.png", "56,00"),
    ("495500-buddhafruit.png", "52,00"),
    ("60751-yellowlightning.png", "48,00"),
    ("477691-mythicalscroll.png", "41,00"),
    ("568986-purplelighting.png", "35,00"),
    ("200503-icefruit.png", "25,00"),
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.getenv("DATABASE_PATH", str(PROJECT_DIR / "instance" / "pixelplaza.sqlite")),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def validate_post_token() -> None:
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                abort(400, description="O formulário expirou. Recarregue a página e tente novamente.")

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.teardown_appcontext
    def close_db(_error=None) -> None:
        database = g.pop("database", None)
        if database is not None:
            database.close()

    with app.app_context():
        init_db()

    @app.get("/")
    def index():
        products = get_db().execute(
            "SELECT * FROM products WHERE available = 1 ORDER BY featured DESC, created_at DESC, id DESC"
        ).fetchall()
        return render_template(
            "index.html",
            products=products,
            physical_items=PHYSICAL_CATALOG,
            permanent_items=PERMANENT_CATALOG,
        )

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if session.get("is_admin"):
            return redirect(url_for("admin"))

        password_is_configured = bool(app.config["ADMIN_PASSWORD"])
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            username_ok = hmac.compare_digest(username, app.config["ADMIN_USERNAME"])
            password_ok = password_is_configured and hmac.compare_digest(
                password, app.config["ADMIN_PASSWORD"]
            )
            if username_ok and password_ok:
                session.clear()
                session["is_admin"] = True
                flash("Acesso liberado. Bem-vindo ao painel.", "success")
                return redirect(url_for("admin"))
            flash("Credenciais inválidas ou painel ainda não configurado.", "error")

        return render_template("login.html", password_is_configured=password_is_configured)

    @app.post("/admin/logout")
    @admin_required
    def logout():
        session.clear()
        flash("Você saiu do painel.", "success")
        return redirect(url_for("login"))

    @app.get("/admin")
    @admin_required
    def admin():
        products = get_db().execute(
            "SELECT * FROM products ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return render_template("admin.html", products=products)

    @app.route("/admin/produtos/novo", methods=["GET", "POST"])
    @admin_required
    def create_product():
        return save_product()

    @app.route("/admin/produtos/<int:product_id>/editar", methods=["GET", "POST"])
    @admin_required
    def edit_product(product_id: int):
        product = get_db().execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            abort(404)
        return save_product(product)

    @app.post("/admin/produtos/<int:product_id>/excluir")
    @admin_required
    def delete_product(product_id: int):
        cursor = get_db().execute("DELETE FROM products WHERE id = ?", (product_id,))
        get_db().commit()
        if cursor.rowcount:
            flash("Produto removido do catálogo.", "success")
        else:
            flash("Esse produto já foi removido.", "error")
        return redirect(url_for("admin"))

    return app


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def get_db() -> sqlite3.Connection:
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"])
        g.database.row_factory = sqlite3.Row
    return g.database


def init_db() -> None:
    get_db().execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            available INTEGER NOT NULL DEFAULT 1,
            featured INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    get_db().commit()


def save_product(existing_product=None):
    is_edit = existing_product is not None
    if request.method == "GET":
        product = dict(existing_product) if is_edit else {"available": 1, "featured": 0}
        return render_template(
            "product_form.html",
            product=product,
            categories=CATEGORIES,
            errors={},
            is_edit=is_edit,
        )

    product = {
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", ""),
        "description": request.form.get("description", "").strip(),
        "price": request.form.get("price", "").strip(),
        "image_url": request.form.get("image_url", "").strip(),
        "available": 1 if request.form.get("available") == "on" else 0,
        "featured": 1 if request.form.get("featured") == "on" else 0,
    }
    errors = {}
    if not product["name"]:
        errors["name"] = "Informe o nome do produto."
    elif len(product["name"]) > 80:
        errors["name"] = "Use até 80 caracteres."
    if product["category"] not in CATEGORIES:
        errors["category"] = "Escolha uma categoria da lista."
    if len(product["description"]) > 500:
        errors["description"] = "Use até 500 caracteres."
    if len(product["price"]) > 40:
        errors["price"] = "Use até 40 caracteres no campo de preço."
    if len(product["image_url"]) > 500:
        errors["image_url"] = "Use até 500 caracteres no endereço da imagem."
    elif product["image_url"]:
        parsed_url = urlsplit(product["image_url"])
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            errors["image_url"] = "Informe um endereço completo começando com http:// ou https://."

    if errors:
        return (
            render_template(
                "product_form.html",
                product=product,
                categories=CATEGORIES,
                errors=errors,
                is_edit=is_edit,
            ),
            400,
        )

    database = get_db()
    if is_edit:
        database.execute(
            """UPDATE products SET name = ?, category = ?, description = ?, price = ?,
               image_url = ?, available = ?, featured = ? WHERE id = ?""",
            (
                product["name"], product["category"], product["description"],
                product["price"], product["image_url"], product["available"],
                product["featured"], existing_product["id"],
            ),
        )
        flash("Produto atualizado.", "success")
    else:
        database.execute(
            """INSERT INTO products (name, category, description, price, image_url, available, featured)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                product["name"], product["category"], product["description"],
                product["price"], product["image_url"], product["available"],
                product["featured"],
            ),
        )
        flash("Produto adicionado ao catálogo.", "success")
    database.commit()
    return redirect(url_for("admin"))


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
