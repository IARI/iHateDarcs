from config import Cache


def get_releasetest_issues(repo='Doogle Drive Releasetest', max_issues=0, assignee=None):
    def callback():
        from gspread_model.Test import ReleasetestFehlerprotokoll
        return [r.toDict() for r in ReleasetestFehlerprotokoll.all_rows(cycle=False) if
                not assignee or r.PersonEntwicklung == assignee]

    return Cache.get_cache.get_or_set(callback, max_issues, repo=repo, author=assignee)
