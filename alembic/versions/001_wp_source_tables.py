"""WordPress Source: wp_sites, wp_sync_runs, wp_authors, wp_terms, wp_content, wp_content_terms

Revision ID: 001
Revises:
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # wp_sites
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_sites (
            site_id     VARCHAR(64) PRIMARY KEY,
            base_url    VARCHAR(512) NOT NULL,
            name        VARCHAR(255),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("COMMENT ON TABLE wp_sites IS 'Зарегистрированные WordPress-сайты для синхронизации'")

    # wp_sync_runs
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_sync_runs (
            id              BIGSERIAL PRIMARY KEY,
            run_id          VARCHAR(32) NOT NULL,
            site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
            started_at      TIMESTAMPTZ NOT NULL,
            finished_at     TIMESTAMPTZ,
            status          VARCHAR(20) NOT NULL DEFAULT 'running',
            error_code      VARCHAR(64),
            posts_count     INT NOT NULL DEFAULT 0,
            pages_count     INT NOT NULL DEFAULT 0,
            terms_count     INT NOT NULL DEFAULT 0,
            authors_count   INT NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_site_started ON wp_sync_runs(site_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_run_id ON wp_sync_runs(run_id)")
    op.execute("COMMENT ON TABLE wp_sync_runs IS 'История запусков WP sync для наблюдаемости и отладки'")

    # wp_authors
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_authors (
            site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
            wp_user_id      BIGINT NOT NULL,
            login           VARCHAR(255),
            name            VARCHAR(255),
            slug            VARCHAR(255),
            raw_json        JSONB,
            synced_at       TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (site_id, wp_user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_authors_site ON wp_authors(site_id)")

    # wp_terms
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_terms (
            site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
            taxonomy        VARCHAR(64) NOT NULL,
            wp_term_id      BIGINT NOT NULL,
            name            VARCHAR(255),
            slug            VARCHAR(255) NOT NULL,
            parent_id       BIGINT,
            raw_json        JSONB,
            synced_at       TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (site_id, taxonomy, wp_term_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_terms_site_tax ON wp_terms(site_id, taxonomy)")

    # wp_content
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_content (
            site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
            content_type    VARCHAR(16) NOT NULL,
            wp_id           BIGINT NOT NULL,
            title           TEXT,
            slug            VARCHAR(255) NOT NULL,
            post_content    TEXT,
            excerpt         TEXT,
            status          VARCHAR(20) NOT NULL DEFAULT 'publish',
            author_id       BIGINT,
            published_at    TIMESTAMPTZ,
            modified_at     TIMESTAMPTZ,
            seo_title       VARCHAR(255),
            seo_description TEXT,
            seo_json        JSONB,
            raw_json        JSONB,
            synced_at       TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (site_id, content_type, wp_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_content_site_type ON wp_content(site_id, content_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_content_published ON wp_content(site_id, published_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_content_slug ON wp_content(site_id, content_type, slug)")

    # wp_content_terms
    op.execute("""
        CREATE TABLE IF NOT EXISTS wp_content_terms (
            site_id         VARCHAR(64) NOT NULL,
            content_type    VARCHAR(16) NOT NULL,
            wp_content_id   BIGINT NOT NULL,
            taxonomy        VARCHAR(64) NOT NULL,
            wp_term_id      BIGINT NOT NULL,
            synced_at       TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (site_id, content_type, wp_content_id, taxonomy, wp_term_id),
            FOREIGN KEY (site_id, content_type, wp_content_id)
                REFERENCES wp_content(site_id, content_type, wp_id) ON DELETE CASCADE,
            FOREIGN KEY (site_id, taxonomy, wp_term_id)
                REFERENCES wp_terms(site_id, taxonomy, wp_term_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wp_content_terms_term ON wp_content_terms(site_id, taxonomy, wp_term_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wp_content_terms")
    op.execute("DROP TABLE IF EXISTS wp_content")
    op.execute("DROP TABLE IF EXISTS wp_terms")
    op.execute("DROP TABLE IF EXISTS wp_authors")
    op.execute("DROP TABLE IF EXISTS wp_sync_runs")
    op.execute("DROP TABLE IF EXISTS wp_sites")
