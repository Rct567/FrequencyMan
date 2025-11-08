import nox

nox.options.default_venv_backend = "uv"

@nox.session(python=["3.9", "3.11", "3.13"])
def test(session: nox.Session):

    session.install("-r", "requirements-dev.txt")
    session.run("pytest", "tests/")
