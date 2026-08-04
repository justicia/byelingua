import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from openai import OpenAI


client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)


def extract_article_text(url: str) -> str:
    parsed_url = urlparse(url)

    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("只支持 http 或 https 链接。")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/150.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for element in soup(
        ["script", "style", "nav", "footer", "header", "aside"]
    ):
        element.decompose()

    article_container = (
        soup.find("article")
        or soup.find("main")
        or soup
    )

    paragraphs = article_container.find_all("p")

    text_parts = []
    seen = set()

    for paragraph in paragraphs:
        text = paragraph.get_text(
            " ",
            strip=True,
        )

        if len(text) < 40:
            continue

        if text in seen:
            continue

        text_parts.append(text)
        seen.add(text)

    article_text = "\n".join(text_parts)

    if not article_text:
        raise ValueError("未能从该页面提取正文。")

    return article_text[:12000]


def translate_article(
    article_text: str,
    target_language: str,
    mode: str,
) -> str:
    if mode == "summary":
        instruction = f"""
请将下面文章总结为{target_language}。

要求：
1. 控制在200至350字。
2. 保留重要人名、作品名、机构名和时间。
3. 只使用原文信息，不自行补充。
4. 如果是评论文章，概括作者的主要评价。
5. 只输出结果正文。
"""
    else:
        instruction = f"""
请将下面文章翻译为{target_language}。

要求：
1. 准确、自然，不逐字硬译。
2. 保留原文段落结构。
3. 准确保留人名、作品名和机构名。
4. 不增加解释或评论。
5. 只输出译文。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=f"""
{instruction}

原文：

{article_text}
""",
    )

    return response.output_text.strip()


class handler(BaseHTTPRequestHandler):

        def do_GET(self):
        message = "Python API is working."

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def send_json(
        self,
        status_code: int,
        payload: dict,
    ) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status_code)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

            raw_body = self.rfile.read(
                content_length
            )

            data = json.loads(
                raw_body.decode("utf-8")
            )

            url = data.get(
                "url",
                "",
            ).strip()

            target_language = data.get(
                "target_language",
                "简体中文",
            ).strip()

            mode = data.get(
                "mode",
                "translate",
            ).strip()

            if not url:
                self.send_json(
                    400,
                    {
                        "error": "请输入文章网址。"
                    },
                )
                return

            if mode not in {
                "translate",
                "summary",
            }:
                self.send_json(
                    400,
                    {
                        "error": "无效的处理模式。"
                    },
                )
                return

            article_text = extract_article_text(
                url
            )

            result = translate_article(
                article_text,
                target_language,
                mode,
            )

            self.send_json(
                200,
                {
                    "result": result,
                    "characters": len(
                        article_text
                    ),
                },
            )

        except requests.RequestException as error:
            self.send_json(
                400,
                {
                    "error": (
                        "无法读取该网页："
                        f"{str(error)}"
                    )
                },
            )

        except Exception as error:
            self.send_json(
                500,
                {
                    "error": str(error)
                },
            )
