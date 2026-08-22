import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context
from src.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Connection string đọc từ .env (KHÔNG hardcode trong alembic.ini/env.py),
# theo CLAUDE.md mục 6 — không đưa mật khẩu thật vào file commit.
# Không đi qua config.set_main_option()/alembic.ini: ConfigParser diễn giải
# ký tự "%" (xuất hiện sau khi url-encode mật khẩu) như cú pháp interpolation
# và ném lỗi — nên engine được tạo trực tiếp bằng create_engine() bên dưới.
load_dotenv()
DB_URL = (
    f"mysql+mysqlconnector://{quote_plus(os.environ['MYSQL_USER'])}:"
    f"{quote_plus(os.environ['MYSQL_PASSWORD'])}@{os.environ['MYSQL_HOST']}:"
    f"{os.environ['MYSQL_PORT']}/{os.environ['MYSQL_DATABASE']}"
)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
