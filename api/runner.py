import argparse


def main(
    host: str = "0.0.0.0",
    port: int = 18200,
    reload: bool = False,
    log_level: str = "info",
    prefix: str = "",
) -> None:
    create_app = __import__("api.api_app", fromlist=["create_app"]).create_app
    uvicorn = __import__("uvicorn")
    app = create_app(store=None, url_prefix=prefix or "")
    uvicorn.run(app, host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18200)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    main(host=args.host, port=args.port, reload=args.reload, log_level=args.log_level, prefix=args.prefix)
