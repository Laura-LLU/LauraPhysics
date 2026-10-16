from exam_pdf import export_stem


def test_auto_name_describes_actual_selection_and_roles_share_stem():
    selected = [{"topic": f"{number} {label}"} for number, label in [
        ("14", "Electric fields"), ("09", "Electricity"),
        ("15", "Capacitance"), ("10", "D.C. circuits"),
    ]]
    stem = export_stem({"title": "OPBP Bank · Electricity 等 专项练习"}, selected)
    assert stem == "Electricity"


def test_filename_stays_short_even_when_teacher_title_is_long():
    stem = export_stem({"title": "高二周测"}, [{"topic": "03 Dynamics"}])
    assert stem == "Dynamics"


def test_filename_cannot_escape_export_folder_and_fits_byte_limit():
    stem = export_stem({"title": "../" + "班级周测" * 100 + "/坏名字:*?"},
                       [{"topic": "03 Dynamics"}])
    assert not stem.startswith(".")
    assert all(char not in stem for char in '/\\:*?"<>|')
    assert stem.isascii()
    assert len((stem + "_Answers.pdf").encode("utf-8")) < 80


def test_all_topic_paper_has_bounded_but_informative_summary():
    stem = export_stem({}, [{"topic": f"{i:02d} Topic"} for i in range(1, 18)])
    assert stem == "Physics"
