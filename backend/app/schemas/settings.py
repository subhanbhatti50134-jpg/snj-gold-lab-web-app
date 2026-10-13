from pydantic import RootModel


class SettingsOut(RootModel[dict[str, str]]):
    pass


class SettingsUpdate(RootModel[dict[str, str]]):
    pass
