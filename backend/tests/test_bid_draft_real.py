"""真实招标文件端到端联调（T11）：三份真实 tender（GZ511 磋商 .docx /
谈判采购文件 .doc（Word COM 归一化）/ JY22 比选 .docx）走完整管线——
上传 → generate（自动定位格式章节）→ 分类断言 → 全部非 ignore 建议确认
→ export-template → X-Fill-Report 可解析且 verify.ok=true。

全部用例按 fixture 存在性 skipif 门控（fixtures 不入库，缺失即跳过）；
jiaotong 用例在本机无 Word（.doc 归一化失败）时跳过。
"""
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.db import Database
from app.deps import get_db
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
GZ511 = FIXTURES / "gz511.docx"        # 磋商类（约 337KB）
JIAOTONG = FIXTURES / "jiaotong.doc"   # 谈判类 .doc（约 1MB，归一化走 Word COM）
JY22 = FIXTURES / "jy22.docx"          # 比选类（约 69KB）

requires_gz511 = pytest.mark.skipif(not GZ511.exists(),
                                    reason="未提供真实招标文件 gz511.docx")
requires_jiaotong = pytest.mark.skipif(not JIAOTONG.exists(),
                                       reason="未提供真实招标文件 jiaotong.doc")
requires_jy22 = pytest.mark.skipif(not JY22.exists(),
                                   reason="未提供真实招标文件 jy22.docx")


@pytest.fixture()
def client(db_path):
    def override():
        db = Database(db_path)
        db.init_schema()
        yield db
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_project(client, name):
    return client.post("/api/projects", json={"name": name}).json()["id"]


def _make_person(client, name, fields=None):
    return client.post("/api/assets", json={
        "type": "person", "name": name, "fields": fields or {}}).json()["id"]


def _make_contract(client, name, fields=None):
    return client.post("/api/assets", json={
        "type": "contract", "name": name, "fields": fields or {}}).json()["id"]


def _upload_tender(client, pid, path: Path):
    with open(path, "rb") as f:
        r = client.post(f"/api/projects/{pid}/tender",
                        files={"file": (path.name, f.read())})
    assert r.status_code == 200, r.text
    return r


def _generate(client, pid):
    r = client.post(f"/api/projects/{pid}/bid-draft/generate", json={})
    return r


def _confirm_all_suggestions(client, pid, gen):
    """把分类建议里 role≠ignore 的全部 confirmed=true 提交（模拟用户全确认）。"""
    tables = [{"table_index": t["table_index"], "role": t["role"],
               "columns": t["columns"],
               "person_scope": t.get("person_scope") or "all",
               "perf_scope": t.get("perf_scope") or "all",
               "label_kind": t.get("label_kind") or "",
               "person": t.get("person") or "",
               "confirmed": True}
              for t in gen["tables"] if t["role"] != "ignore"]
    r = client.put(f"/api/projects/{pid}/bid-draft/bindings",
                   json={"tables": tables,
                         "swap_toc": bool(gen.get("swap_toc"))})
    assert r.status_code == 200, r.text


def _seed_assets(client):
    """两名人员（张三负责）+ 两份合同（项目A section1 负责人张三 / 项目B section2）。"""
    zhang = _make_person(client, "张三", {
        "职称": "高级工程师", "性别": "男", "年龄": "42", "学历": "本科",
        "证书": [{"类型": "一级造价师", "专业": "土建", "有效期至": "2027-01-01"}]})
    li = _make_person(client, "李四", {"职称": "工程师"})
    ca = _make_contract(client, "项目A", {
        "类型": "跟踪", "委托单位": "甲公司", "签订日期": "2024-03-15",
        "项目负责人": "张三"})
    cb = _make_contract(client, "项目B", {
        "类型": "结算", "委托单位": "乙公司", "签订日期": "2023-01-01",
        "项目负责人": "王五"})
    return zhang, li, ca, cb


def _export(client, pid, zhang, li, ca, cb):
    r = client.post(
        f"/api/projects/{pid}/bid-assets/export-template",
        json={"persons": [{"asset_id": zhang, "is_lead": True},
                          {"asset_id": li, "is_lead": False}],
              "contracts": [{"asset_id": ca, "section": 1},
                            {"asset_id": cb, "section": 2}],
              "project_no": "REAL-2026-001",
              "project_name": "真实联调项目XYZ",
              "doc_date": "2026-09-08"})
    assert r.status_code == 200, r.text
    header = r.headers.get("x-fill-report")
    assert header, "有底稿导出必须带 X-Fill-Report"
    return r, json.loads(unquote(header))


# ---------- 1. GZ511（磋商 .docx） ----------

@requires_gz511
def test_gz511_generate_and_classify(client, tmp_path):
    pid = _make_project(client, "GZ511真实联调")
    _upload_tender(client, pid, GZ511)
    gen = _generate(client, pid)
    assert gen.status_code == 200, gen.text
    data = gen.json()
    assert "格式" in data["cut_start"]
    roles = [t["role"] for t in data["tables"]]
    assert roles.count("person_roster") >= 1   # 九、项目组人员表
    assert roles.count("perf_list") >= 1       # 十一、业绩（项目单位关键词）
    assert "quote" in roles                    # 五、磋商响应报价表
    # 十、项目负责人简历表：真实文件为 17 列合并网格（标签横排+内嵌业绩子表），
    # 超出一期 lead_resume 键值模型；实际分类为 person_roster/scope=lead，
    # 如实记录（详见 task-11-report）
    resume = [t for t in data["tables"] if "简历" in t["context_heading"]]
    assert resume and resume[0]["role"] == "person_roster"
    assert resume[0]["person_scope"] == "lead"
    roster = [t for t in data["tables"] if "项目组人员" in t["context_heading"]]
    assert roster and roster[0]["role"] == "person_roster"
    assert roster[0]["columns"].get("gender") is not None
    assert roster[0]["columns"].get("age") is not None


@requires_gz511
def test_gz511_export_verify_ok(client, tmp_path):
    pid = _make_project(client, "GZ511真实联调")
    _upload_tender(client, pid, GZ511)
    gen = _generate(client, pid).json()
    _confirm_all_suggestions(client, pid, gen)
    zhang, li, ca, cb = _seed_assets(client)
    r, report = _export(client, pid, zhang, li, ca, cb)
    assert report["verify"]["ok"] is True, report["verify"]["issues"]
    # quote 表进 skipped
    assert any(s.get("role") == "quote" for s in report["skipped"])
    # 人员表确实被填充
    assert any(f["role"] == "person_roster" and f["rows"] >= 1
               for f in report["filled"])
    doc = Document(BytesIO(r.content))
    assert doc.tables  # 产物可解析


# ---------- 2. 交通局（谈判 .doc，Word COM 归一化） ----------

@requires_jiaotong
def test_jiaotong_generate_and_classify(client, tmp_path):
    pid = _make_project(client, "谈判真实联调")
    _upload_tender(client, pid, JIAOTONG)
    gen = _generate(client, pid)
    if gen.status_code == 422 and ("Word" in gen.text or "无法转换" in gen.text):
        pytest.skip("本机无 Word，.doc 归一化不可用")
    assert gen.status_code == 200, gen.text
    data = gen.json()
    assert "格式" in data["cut_start"]
    roles = [t["role"] for t in data["tables"]]
    assert "quote" in roles                    # 三、谈判响应报价表
    assert "person_roster" in roles            # 四、拟派投入人员一览表
    roster = [t for t in data["tables"]
              if t["role"] == "person_roster"
              and "拟派投入人员" in t["context_heading"]
              and "gender" in t["columns"]]
    assert roster, "拟派投入人员一览表应映射多列语义"
    cols = roster[0]["columns"]
    assert {"gender", "age", "education"} <= set(cols)  # 多列语义
    assert "name" in cols and "title" in cols


@requires_jiaotong
def test_jiaotong_export_verify_ok_quote_skipped(client, tmp_path):
    """导出 + quote skipped 断言；同时是 .doc Word COM 二次转换回归
    （同进程第二次 ensure_docx 曾因线程未 CoInitialize 失败，
    修复见 input_convert._convert_doc）。"""
    pid = _make_project(client, "谈判真实联调")
    _upload_tender(client, pid, JIAOTONG)
    gen = _generate(client, pid)
    if gen.status_code == 422 and ("Word" in gen.text or "无法转换" in gen.text):
        pytest.skip("本机无 Word，.doc 归一化不可用")
    _confirm_all_suggestions(client, pid, gen.json())
    zhang, li, ca, cb = _seed_assets(client)
    r, report = _export(client, pid, zhang, li, ca, cb)
    assert report["verify"]["ok"] is True, report["verify"]["issues"]
    quote_skips = [s for s in report["skipped"] if s.get("role") == "quote"]
    assert quote_skips
    assert quote_skips[0]["reason"] == "报价表需手工填写"


# ---------- 3. JY22（比选 .docx） ----------

@requires_jy22
def test_jy22_generate_and_export(client, tmp_path):
    pid = _make_project(client, "JY22真实联调")
    _upload_tender(client, pid, JY22)
    gen = _generate(client, pid)
    assert gen.status_code == 200, gen.text
    data = gen.json()
    assert "格式" in data["cut_start"]
    roles = [t["role"] for t in data["tables"]]
    # 比选文件以文字条款为主：少量非 ignore（人员配备/类似业绩一览表），无 quote
    non_ignore = [r for r in roles if r != "ignore"]
    assert len(non_ignore) <= 2
    assert "quote" not in roles
    _confirm_all_suggestions(client, pid, data)
    zhang, li, ca, cb = _seed_assets(client)
    r, report = _export(client, pid, zhang, li, ca, cb)
    assert report["verify"]["ok"] is True, report["verify"]["issues"]
