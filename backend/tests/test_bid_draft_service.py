"""底稿驱动商务标导出：列语义数据组装测试（bid_service 扩展，Task 6）。
覆盖 person_semantics / contract_semantics 逐键语义、空字段容错、
assemble_bid_draft_data 的证书勾选过滤/role 补全/负责人业绩文本。"""
import pytest

from app.db import Database
from app.services import bid_service
from app.services.bid_service import (
    PERF_SEM_KEYS,
    PERSON_SEM_KEYS,
    assemble_bid_draft_data,
    contract_semantics,
    effective_work_years,
    person_semantics,
    _cert_qualifications,
)


@pytest.fixture()
def db(db_path):
    database = Database(db_path)
    database.init_schema()
    return database


def _person_fields(**overrides):
    fields = {
        "性别": "男",
        "年龄": "40",
        "学历": "本科",
        "职称": "高级工程师",
        "从业年限": "15",
        "从业年限基准年": "2024",
        "证书": [{"类型": "一级造价师", "专业": "土建", "有效期至": "2027-01-01"},
                 {"类型": "监理工程师", "有效期至": "2028-01-01"}],
    }
    fields.update(overrides)
    return fields


# ---------- person_semantics ----------

def test_person_semantics_lead_full_fields():
    p = {"name": "张三", "fields": _person_fields(), "is_lead": True}
    sem = person_semantics(p, 1, role="项目经理")
    assert sem["seq"] == "1"
    assert sem["label"] == "1.项目负责人"
    assert sem["name"] == "张三"
    assert sem["gender"] == "男"
    assert sem["age"] == "40"
    assert sem["education"] == "本科"
    assert sem["title"] == "高级工程师"
    assert sem["work_years"] == effective_work_years(p["fields"])
    assert sem["work_years"].endswith("年")
    assert sem["certs"] == _cert_qualifications(p["fields"])
    assert "土建专业一级造价师" in sem["certs"]
    assert sem["role"] == "项目经理"
    assert set(sem.keys()) == set(PERSON_SEM_KEYS)


def test_person_semantics_non_lead_label_and_default_role():
    p = {"name": "李四", "fields": _person_fields(), "is_lead": False}
    sem = person_semantics(p, 3)
    assert sem["label"] == "3.项目组其他人员"
    assert sem["role"] == ""


def test_person_semantics_empty_fields_no_error():
    sem = person_semantics({"name": "王五", "fields": {}, "is_lead": False}, 2)
    assert sem["name"] == "王五"
    assert sem["label"] == "2.项目组其他人员"
    for key in ("gender", "age", "education", "title", "work_years",
                "certs", "role"):
        assert sem[key] == ""
    # fields 缺失键也不抛错
    sem2 = person_semantics({"name": "赵六", "fields": {"职称": "工程师"}},
                            1)
    assert sem2["title"] == "工程师"
    assert sem2["gender"] == "" and sem2["certs"] == ""


# ---------- contract_semantics ----------

def test_contract_semantics_full_fields():
    c = {"name": "项目A", "section": 1, "fields": {
        "类型": "跟踪", "委托单位": "甲公司", "签订日期": "2024-03-15",
        "工程造价（万元）": "1200", "合同金额": "1300",
        "项目类型": "市政"}}
    sem = contract_semantics(c, 1)
    assert sem["seq"] == "1"
    assert sem["project_name"] == "项目A"
    assert sem["client"] == "甲公司"
    assert sem["sign_date"] == "2024-03-15"
    assert sem["amount"] == "1200"  # 工程造价（万元）优先于 合同金额
    assert sem["service_type"] == "跟踪审计"
    assert sem["content"] == "提供项目A的跟踪审计服务"
    assert sem["project_type"] == "市政"
    assert sem["client_contact"] == ""
    assert sem["proof_page"] == ""
    assert set(sem.keys()) == set(PERF_SEM_KEYS)


def test_contract_semantics_amount_fallback_and_empty():
    c = {"name": "项目B", "fields": {"类型": "结算", "合同金额": "500"}}
    sem = contract_semantics(c, 2)
    assert sem["amount"] == "500"  # 无工程造价（万元）时回落合同金额
    assert sem["service_type"] == "结算审核"
    assert sem["content"] == "提供项目B的结算审核服务"
    assert sem["sign_date"] == "" and sem["client"] == ""
    sem_empty = contract_semantics({"name": "项目C", "fields": {}}, 3)
    assert sem_empty["amount"] == "" and sem_empty["service_type"] == ""


# ---------- assemble_bid_draft_data ----------

def _seed(db):
    """两名人员（张三负责）+ 三份合同（A/B/C；A/C 项目负责人=张三）。"""
    pid = db.create_project("底稿项目")
    zhang = db.create_asset("person", "张三", _person_fields())
    li = db.create_asset("person", "李四", {
        "职称": "工程师",
        "证书": [{"类型": "一级建造师", "专业": "建筑工程"}]})
    a = db.create_asset("contract", "项目A", {
        "类型": "跟踪", "委托单位": "甲公司", "签订日期": "2024-03-15",
        "项目负责人": "张三"})
    b = db.create_asset("contract", "项目B", {
        "类型": "结算", "委托单位": "乙公司", "签订日期": "2023-01-01",
        "项目负责人": "王五"})
    c = db.create_asset("contract", "项目C", {
        "类型": "编标", "委托单位": "丙公司", "签订日期": "2022-06-01",
        "项目负责人": "张三", "年份": "2022"})
    return pid, zhang, li, a, b, c


def test_assemble_bid_draft_data_basic(db):
    pid, zhang, li, ca, cb, cc = _seed(db)
    # 先保存勾选（带 role），再走 picks 组装
    db.replace_project_assets(
        pid,
        [{"asset_id": zhang, "role": "项目经理", "is_lead": True},
         {"asset_id": li, "role": "组员"}],
        [{"asset_id": ca, "section": 1}, {"asset_id": cb, "section": 1},
         {"asset_id": cc, "section": 2}])
    data = assemble_bid_draft_data(
        db, pid,
        person_picks=[{"asset_id": li, "is_lead": False},
                      {"asset_id": zhang, "is_lead": True}],
        contract_picks=[{"asset_id": ca, "section": 1},
                        {"asset_id": cb, "section": 1},
                        {"asset_id": cc, "section": 2}])
    persons = data["persons"]
    # 负责人优先稳定排序 + role 从已保存勾选补全
    assert [p["name"] for p in persons] == ["张三", "李四"]
    assert persons[0]["is_lead"] is True and persons[0]["role"] == "项目经理"
    assert persons[1]["role"] == "组员"
    # 每项含 sem 且键集合符合语义键
    for p in persons:
        assert set(p["sem"].keys()) <= set(PERSON_SEM_KEYS)
    assert persons[0]["sem"]["label"] == "1.项目负责人"
    assert persons[0]["sem"]["seq"] == "1"
    assert persons[1]["sem"]["label"] == "2.项目组其他人员"
    contracts = data["contracts"]
    assert [c["name"] for c in contracts] == ["项目A", "项目B", "项目C"]
    for c in contracts:
        assert set(c["sem"].keys()) <= set(PERF_SEM_KEYS)
    assert contracts[0]["sem"]["content"] == "提供项目A的跟踪审计服务"
    assert contracts[0]["sem"]["seq"] == "1"
    # 负责人业绩文本：仅张三名下（A、C），逐行 项目名称（年份）
    assert data["lead_perfs_text"] == "项目A（2024）\n项目C（2022）"


def test_assemble_bid_draft_data_certs_filter(db):
    """certs 过滤语义与 assemble_bid_template_data 一致：
    None 保留全部 / [] 为空 / [k] 只含第 k 个。"""
    pid, zhang, _, _, _, _ = _seed(db)

    def certs_text(pick):
        data = assemble_bid_draft_data(db, pid, person_picks=[pick],
                                       contract_picks=[])
        return data["persons"][0]["sem"]["certs"]

    full = certs_text({"asset_id": zhang, "is_lead": True})
    assert "土建专业一级造价师" in full and "监理工程师" in full
    assert certs_text({"asset_id": zhang, "is_lead": True,
                       "certs": None}) == full
    assert certs_text({"asset_id": zhang, "is_lead": True,
                       "certs": []}) == ""
    only = certs_text({"asset_id": zhang, "is_lead": True, "certs": [1]})
    assert only == "监理工程师"
    # 原始资产 fields 不被污染
    assert len(db.get_asset(zhang)["fields"]["证书"]) == 2


def test_assemble_bid_draft_data_no_lead(db):
    pid, _, li, ca, _, _ = _seed(db)
    data = assemble_bid_draft_data(
        db, pid,
        person_picks=[{"asset_id": li}],
        contract_picks=[{"asset_id": ca, "section": 1}])
    assert data["lead_perfs_text"] == ""
    assert data["persons"][0]["sem"]["label"] == "1.项目组其他人员"


def test_assemble_bid_draft_data_lead_without_matching_perf(db):
    pid, zhang, _, _, cb, _ = _seed(db)
    data = assemble_bid_draft_data(
        db, pid,
        person_picks=[{"asset_id": zhang, "is_lead": True}],
        contract_picks=[{"asset_id": cb, "section": 1}])  # 项目负责人=王五
    assert data["lead_perfs_text"] == ""


def test_assemble_bid_draft_data_role_missing_when_not_saved(db):
    """勾选未保存过时 role 回落为空串，不抛错。"""
    pid, zhang, _, _, _, _ = _seed(db)
    data = assemble_bid_draft_data(
        db, pid, person_picks=[{"asset_id": zhang, "is_lead": True}],
        contract_picks=[])
    assert data["persons"][0]["role"] == ""
