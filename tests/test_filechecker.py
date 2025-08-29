import pytest
import csv
from pathlib import Path
import mylar
from mylar import filechecker


def empty_string_to_none(input):
    return None if input == '' else input


def none_string_to_none(input):
    return None if input == 'None' else input


def load_filename_parsing_tests():
    test_filechecker_data = Path(Path(__file__).parents[0], "data", "filename_tests.csv")

    test_list = []

    with open(test_filechecker_data) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"', )
        entry_counter = 0
        for entry in reader:
            entry_counter += 1
            test_id = f"{entry_counter:03}:{entry['filename']}"
            
            test_list.append(
                pytest.param(entry['filename'], entry['series'], none_string_to_none(entry['issue']),
                             none_string_to_none(entry['year']), none_string_to_none(entry['volume']),
                             (entry['xfail'].lower() == "true"), id=test_id))
            # Retaining for reference - alternative approach to expected failures to report them (and unexpected passes) but not
            # fail the suite.
            # if entry['xfail'].lower() == "true":
            #     test_list.append(
            #         pytest.param(entry['filename'], entry['series'], none_string_to_none(entry['issue']),
            #                      none_string_to_none(entry['year']), none_string_to_none(entry['volume']),
            #                      True, id=test_id, marks=pytest.mark.xfail(reason=entry['testnotes'])))
            # else:
            #     test_list.append(
            #         pytest.param(entry['filename'], entry['series'], none_string_to_none(entry['issue']),
            #                      none_string_to_none(entry['year']), none_string_to_none(entry['volume']),
            #                      False, id=test_id))

    return test_list


@pytest.mark.parametrize("filename,series,issue,year,volume,xfail", load_filename_parsing_tests())
@pytest.mark.unit
def test_manual_filename_parsing(monkeypatch, filename, series, issue, year, volume, xfail):
    monkeypatch.setattr(mylar, "CONFIG", mylar.config.Config("./nothing"))
    monkeypatch.setattr(mylar.CONFIG, "IGNORE_SEARCH_WORDS", [], raising=False)
    monkeypatch.setattr(mylar.CONFIG, "CUSTOM_ISSUE_EXCEPTIONS", [], raising=False)

    fc_obj = filechecker.FileChecker(file=filename, justparse=True, manual=True)
    parsed = fc_obj.parseit(path='/dummypath/', filename=filename)

    # Rather than multiple asserts and early exit, checks all at once (skipping blanks)
    if xfail:
        assert ((parsed['series_name'] .lower(),
                None if volume is None else parsed['series_volume'],
                None if year is None else parsed['issue_year'],
                None if issue is None else parsed['issue_number'])
                !=
                (series.lower(),
                volume,
                year,
                issue))
    else:
        assert ((parsed['series_name'] .lower(),
                None if volume is None else parsed['series_volume'],
                None if year is None else parsed['issue_year'],
                None if issue is None else parsed['issue_number'])
                ==
                (series.lower(),
                volume,
                year,
                issue))
