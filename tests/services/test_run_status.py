from src.services.status_manager import StatusManager


def main() -> None:

    status_manager = StatusManager()
    status_text = status_manager.get_status_text()
    print(status_text)

main()