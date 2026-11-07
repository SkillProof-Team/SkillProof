"""Strict API input validation; unknown fields are rejected."""

import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import DIMENSION_IDS, ROLE_MAP
from .url_validation import https_url


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


def valid_email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", value) or len(value) > 254:
        raise ValueError("请输入有效的电子邮箱地址")
    if ".." in value or len(value.split("@", 1)[0]) > 64:
        raise ValueError("请输入有效的电子邮箱地址")
    return value


def valid_password(value: str) -> str:
    if not 15 <= len(value) <= 128 or len(value.encode("utf-8")) > 512:
        raise ValueError("密码须为15–128个字符，最多512字节")
    if value.isspace():
        raise ValueError("密码不能只包含空白")
    return value


def valid_name(value: str) -> str:
    value = value.strip()
    if (
        not 1 <= len(value) <= 50
        or not value.isprintable()
        or not any(unicodedata.category(c)[0] in "LNPS" for c in value)
    ):
        raise ValueError("姓名须为1–50个可显示字符")
    return value


class RegisterInput(InputModel):
    email: str = Field(max_length=254)
    name: str = Field(max_length=50)
    password: str = Field(min_length=15, max_length=128)
    _email = field_validator("email")(valid_email)
    _name = field_validator("name")(valid_name)
    _password = field_validator("password")(valid_password)


class LoginInput(InputModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)
    _email = field_validator("email")(valid_email)


class ProfileInput(InputModel):
    name: str | None = Field(default=None, max_length=50)
    targetRole: str | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v):
        if v is None:
            raise ValueError("姓名不可为空")
        return valid_name(v)

    @field_validator("targetRole")
    @classmethod
    def role_valid(cls, v):
        if v is not None and v not in ROLE_MAP:
            raise ValueError("未知岗位")
        return v


class PasswordInput(InputModel):
    currentPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=15, max_length=128)
    _password = field_validator("newPassword")(valid_password)


class DeleteInput(InputModel):
    password: str = Field(min_length=1, max_length=128)


class AttemptInput(InputModel):
    roleId: Literal["backend", "frontend", "algorithm", "qa"]


class AnswersInput(InputModel):
    answers: dict[str, list[Literal["A", "B", "C", "D"]]] = Field(max_length=18)

    @field_validator("answers")
    @classmethod
    def valid_answers(cls, value):
        for qid, selected in value.items():
            if len(qid) > 128 or len(selected) > 4 or len(selected) != len(set(selected)):
                raise ValueError("答案不能重复，题目ID长度受限")
        return value


class TaskInput(InputModel):
    status: Literal["todo", "doing", "done"]
    notes: str | None = Field(default=None, max_length=2000)


class FeedbackInput(InputModel):
    category: Literal["bug", "content", "suggestion"]
    message: str = Field(min_length=5, max_length=4000)
    attemptId: str | None = Field(default=None, max_length=128)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("反馈至少需要5个非首尾空白字符")
        return v.strip()


class FeedbackStatusInput(InputModel):
    status: Literal["open", "resolved"]


class Option(InputModel):
    id: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=3000)


class Source(InputModel):
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=10, max_length=2000)

    @field_validator("url")
    @classmethod
    def https_only(cls, v):
        try:
            https_url(v)
        except ValueError as exc:
            raise ValueError("来源必须使用有效HTTPS链接") from exc
        return v

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, v):
        if not v.strip():
            raise ValueError("来源标题不可仅为空白")
        return v


class QuestionInput(InputModel):
    id: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    dimension: str
    # Optional for older records; retained in server-side T03 snapshots.
    topicId: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]+$")
    topic: str = Field(min_length=1, max_length=100)
    type: Literal["single", "multiple"]
    difficulty: Literal["easy", "medium", "hard"]
    stem: str = Field(min_length=5, max_length=8000)
    options: list[Option] = Field(min_length=4, max_length=4)
    correct: list[Literal["A", "B", "C", "D"]] = Field(min_length=1, max_length=4)
    explanation: str = Field(min_length=5, max_length=8000)
    sources: list[Source] = Field(max_length=10)
    version: int | None = Field(default=None, ge=1)
    status: Literal["published", "draft", "archived"] = "draft"

    @field_validator("dimension")
    @classmethod
    def valid_dimension(cls, v):
        if v not in DIMENSION_IDS:
            raise ValueError("未知知识维度")
        return v

    @model_validator(mode="after")
    def exact_options(self):
        if self.status == "published" and not self.sources:
            raise ValueError("已发布题目必须提供来源")
        if {o.id for o in self.options} != {"A", "B", "C", "D"}:
            raise ValueError("选项ID必须恰为A、B、C、D")
        if len(set(self.correct)) != len(self.correct):
            raise ValueError("正确答案不能重复")
        if self.type == "single" and len(self.correct) != 1:
            raise ValueError("单选题必须只有一个正确选项")
        if self.type == "multiple" and len(self.correct) < 2:
            raise ValueError("多选题必须至少有两个正确选项")
        if (
            any(not o.text.strip() for o in self.options)
            or not self.topic.strip()
            or len(self.stem.strip()) < 5
            or len(self.explanation.strip()) < 5
        ):
            raise ValueError("题干和解析至少需5个非首尾空白字符，知识点和选项不可仅为空白")
        return self
