"""Lazy Selenium adapter for CNYES collection."""
from __future__ import annotations

from typing import Any

from app.research.tw_news_content_relevance import cnyes_search_result_from_dom, normalize_text


class CnyesSeleniumBrowser:
    def __init__(self, driver: Any, *, reference: Any | None = None) -> None:
        self.driver = driver
        self.reference = reference
        self._last_count = 0

    def open_search(self, url: str) -> None:
        self.driver.get(url)

    def wait_results_ready(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(self.driver, 10).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'a[href*="news.cnyes.com/news/id/"]')) > 0)

    def _cards(self) -> list[dict[str, Any]]:
        script = r'''
        const anchors = Array.from(document.querySelectorAll('a[href*="news.cnyes.com/news/id/"]'));
        return anchors.map((a) => {
          const container = a.closest('article, section, div') || a;
          const timeNode = container.querySelector('time,[datetime]');
          return {
            href: a.href || a.getAttribute('href') || '',
            text: (container.innerText || a.innerText || '').trim(),
            datetime_attr: timeNode ? (timeNode.getAttribute('datetime') || timeNode.textContent || '') : ''
          };
        });
        '''
        rows = self.driver.execute_script(script) or []
        cards: list[dict[str, Any]] = []
        for row in rows:
            href = row.get('href') if isinstance(row, dict) else ''
            if not href:
                continue
            cards.append(cnyes_search_result_from_dom(href=href, text=row.get('text', ''), datetime_attr=row.get('datetime_attr'), reference=self.reference))
        self._last_count = len(cards)
        return cards

    def visible_result_cards(self) -> list[dict[str, Any]]:
        return self._cards()

    def scroll_for_more(self, current_count: int) -> list[dict[str, Any]]:
        from selenium.webdriver.support.ui import WebDriverWait
        before = max(current_count, self._last_count)
        self.driver.execute_script('window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));')
        try:
            WebDriverWait(self.driver, 6).until(lambda _d: len(self._cards()) > before)
        except Exception:
            return []
        cards = self._cards()
        return cards[before:]

    def open_article(self, url: str) -> None:
        self.driver.get(url)

    def article_body(self) -> str:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(self.driver, 10).until(lambda d: len(normalize_text(d.find_element(By.TAG_NAME, 'body').text)) > 80)
        return normalize_text(self.driver.find_element(By.TAG_NAME, 'body').text)

    def close(self) -> None:
        self.driver.quit()


def create_cnyes_selenium_browser(*, headless: bool = True) -> CnyesSeleniumBrowser:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,1800')
    driver = webdriver.Chrome(options=options)
    return CnyesSeleniumBrowser(driver)
