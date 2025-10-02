/*
 * Auto Proposal Wire Generator Figma Plugin
 * ----------------------------------------
 * Fetches Wire JSON (either via signed URL or inline upload) and composes
 * desktop/tablet/mobile frames by instancing the internal UI Kit components.
 */

const UI_HTML = String.raw`
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Wire JSON Loader</title>
    <style>
      :root {
        color-scheme: light dark;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      body {
        margin: 0;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      h1 {
        font-size: 14px;
        margin: 0;
      }
      label {
        font-size: 11px;
        font-weight: 600;
      }
      input[type="url"], textarea {
        width: 100%;
        box-sizing: border-box;
        border-radius: 6px;
        border: 1px solid rgba(0,0,0,0.15);
        padding: 8px;
        font-size: 11px;
        background: var(--input-bg, white);
      }
      button {
        font-size: 11px;
        padding: 6px 12px;
        border-radius: 6px;
        border: none;
        cursor: pointer;
      }
      button.primary {
        background: #2563eb;
        color: white;
      }
      button.secondary {
        background: rgba(0,0,0,0.08);
        color: inherit;
      }
      button.danger {
        background: #dc2626;
        color: white;
      }
      .row {
        display: flex;
        gap: 8px;
      }
      .row button {
        flex: 1;
      }
      ul {
        margin: 0;
        padding-left: 16px;
        font-size: 11px;
        max-height: 120px;
        overflow-y: auto;
      }
      #status {
        font-size: 11px;
        min-height: 16px;
      }
      #warnings {
        color: #b45309;
      }
    </style>
  </head>
  <body>
    <h1>Wire JSON インポート</h1>
    <section>
      <label for="json-url">署名付きURL</label>
      <input id="json-url" type="url" placeholder="https://.../wire.json" />
    </section>
    <div class="row">
      <button class="primary" id="load-url">URL を取得</button>
      <button class="secondary" id="clear-url">クリア</button>
    </div>
    <section>
      <label for="file-input">ローカルJSONをアップロード</label>
      <input id="file-input" type="file" accept="application/json" />
    </section>
    <div class="row">
      <button class="secondary" id="replay">最後のURLで再実行</button>
      <button class="danger" id="close">閉じる</button>
    </div>
    <div id="status"></div>
    <section>
      <label>警告</label>
      <ul id="warnings"></ul>
    </section>
    <script>
      const statusEl = document.getElementById('status');
      const urlInput = document.getElementById('json-url');
      const warningsEl = document.getElementById('warnings');
      const fileInput = document.getElementById('file-input');

      function postMessage(type, payload) {
        parent.postMessage({ pluginMessage: { type, ...payload } }, '*');
      }

      document.getElementById('load-url').addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (!url) {
          statusEl.textContent = 'URL を入力してください。';
          return;
        }
        statusEl.textContent = '読み込み中...';
        warningsEl.innerHTML = '';
        postMessage('load-url', { url });
      });

      document.getElementById('clear-url').addEventListener('click', () => {
        urlInput.value = '';
        statusEl.textContent = 'URL をクリアしました。';
        warningsEl.innerHTML = '';
        fileInput.value = '';
        postMessage('clear-url', {});
      });

      document.getElementById('replay').addEventListener('click', () => {
        postMessage('replay-last', {});
      });

      document.getElementById('close').addEventListener('click', () => {
        postMessage('close', {});
      });

      fileInput.addEventListener('change', async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        statusEl.textContent = 'ファイルを読み込み中...';
        warningsEl.innerHTML = '';
        try {
          const text = await file.text();
          postMessage('load-inline-json', { json: text, filename: file.name });
        } catch (err) {
          statusEl.textContent = 'ファイル読み込みでエラーが発生しました。';
        }
      });

      onmessage = (event) => {
        const msg = event.data.pluginMessage;
        if (!msg) return;
        if (msg.type === 'init') {
          if (msg.lastUrl) {
            urlInput.value = msg.lastUrl;
            statusEl.textContent = '最後に使用したURLを読み込み済み。';
          }
        }
        if (msg.type === 'status') {
          statusEl.textContent = msg.message || '';
        }
        if (msg.type === 'warnings') {
          warningsEl.innerHTML = '';
          for (const warning of msg.items || []) {
            const li = document.createElement('li');
            li.textContent = warning;
            warningsEl.appendChild(li);
          }
        }
        if (msg.type === 'complete') {
          statusEl.textContent = 'ワイヤーフレームを生成しました。';
          if (msg.warnings && msg.warnings.length === 0) {
            const li = document.createElement('li');
            li.textContent = '警告はありません。';
            warningsEl.appendChild(li);
          }
        }
        if (msg.type === 'error') {
          statusEl.textContent = msg.message || 'エラーが発生しました。';
        }
      };
    </script>
  </body>
</html>
`;

interface WireDraft {
  project: { id: string; title: string };
  frames?: string[];
  pages: WirePage[];
}

interface WirePage {
  page_id: string;
  sections: WireSection[];
  notes?: string[];
}

interface WireSection {
  kind: string;
  variant: string;
  placeholders?: Record<string, string>;
}

interface FramePreset {
  name: string;
  width: number;
  baseHeight: number;
  padding: { top: number; bottom: number; horizontal: number };
  sectionSpacing: number;
  layoutGrid?: LayoutGrid;
}

const FRAME_PRESETS: Record<string, FramePreset> = {
  Desktop: {
    name: 'Desktop',
    width: 1440,
    baseHeight: 1024,
    padding: { top: 96, bottom: 120, horizontal: 160 },
    sectionSpacing: 40,
    layoutGrid: {
      pattern: 'COLUMNS',
      alignment: 'STRETCH',
      gutterSize: 32,
      count: 12,
      sectionSize: 72,
      offset: 0,
      visible: true,
      color: { r: 0.85, g: 0.85, b: 0.85 }
    }
  },
  Tablet: {
    name: 'Tablet',
    width: 1024,
    baseHeight: 1200,
    padding: { top: 80, bottom: 100, horizontal: 96 },
    sectionSpacing: 32,
    layoutGrid: {
      pattern: 'COLUMNS',
      alignment: 'STRETCH',
      gutterSize: 24,
      count: 8,
      sectionSize: 72,
      offset: 0,
      visible: true,
      color: { r: 0.85, g: 0.85, b: 0.85 }
    }
  },
  Mobile: {
    name: 'Mobile',
    width: 390,
    baseHeight: 1600,
    padding: { top: 64, bottom: 96, horizontal: 24 },
    sectionSpacing: 24,
    layoutGrid: {
      pattern: 'COLUMNS',
      alignment: 'STRETCH',
      gutterSize: 16,
      count: 4,
      sectionSize: 60,
      offset: 0,
      visible: true,
      color: { r: 0.85, g: 0.85, b: 0.85 }
    }
  }
};

const DEFAULT_FRAME_ORDER = ['Desktop', 'Tablet', 'Mobile'];

figma.showUI(UI_HTML, { width: 360, height: 480 });

void (async () => {
  const lastUrl = await figma.clientStorage.getAsync('wireDraft:lastUrl');
  figma.ui.postMessage({ type: 'init', lastUrl });
})();

figma.root.setRelaunchData({ 'regenerate-wire': 'Regenerate wireframe from JSON' });

figma.ui.onmessage = async (msg: { type: string; [key: string]: unknown }) => {
  switch (msg.type) {
    case 'load-url':
      await handleUrlRequest(String(msg.url ?? ''));
      break;
    case 'load-inline-json':
      await handleInlineJson(String(msg.json ?? ''), String(msg.filename ?? 'local.json'));
      break;
    case 'replay-last':
      await replayLastUrl();
      break;
    case 'clear-url':
      await figma.clientStorage.setAsync('wireDraft:lastUrl', '');
      break;
    case 'close':
      figma.closePlugin('プラグインを終了しました。');
      break;
    default:
      console.warn('Unknown message from UI', msg);
  }
};

async function handleUrlRequest(url: string) {
  if (!url) {
    pushStatus('URL が指定されていません。');
    return;
  }
  pushStatus('Wire JSON を取得しています...');
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const text = await response.text();
    await figma.clientStorage.setAsync('wireDraft:lastUrl', url);
    await processWireJson(text, { source: 'url', identifier: url });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    pushError(`取得に失敗しました: ${message}`);
  }
}

async function handleInlineJson(json: string, filename: string) {
  if (!json.trim()) {
    pushStatus('JSON の内容が空です。');
    return;
  }
  pushStatus(`${filename} を解析中...`);
  try {
    await processWireJson(json, { source: 'file', identifier: filename });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    pushError(`解析に失敗しました: ${message}`);
  }
}

async function replayLastUrl() {
  const lastUrl = (await figma.clientStorage.getAsync('wireDraft:lastUrl')) as string | undefined;
  if (!lastUrl) {
    pushStatus('前回のURLが見つかりません。');
    return;
  }
  await handleUrlRequest(lastUrl);
}

async function processWireJson(json: string, meta: { source: 'url' | 'file'; identifier: string }) {
  try {
    const data = JSON.parse(json) as WireDraft;
    validateWireDraft(data);
    pushStatus('ワイヤーフレームを生成中...');
    const result = await generateWireframes(data);
    pushStatus(`生成が完了しました (${meta.source === 'url' ? meta.identifier : 'ローカルファイル'})`);
    figma.ui.postMessage({ type: 'complete', warnings: result.warnings, frames: result.frames });
    if (result.warnings.length) {
      pushWarnings(result.warnings);
      figma.notify(`警告あり: ${result.warnings.length}件`, { timeout: 4000 });
    } else {
      figma.notify('Wire JSON から生成が完了しました。');
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    pushError(message);
  }
}

function validateWireDraft(data: WireDraft) {
  if (!data || typeof data !== 'object') {
    throw new Error('Wire JSON が不正です。');
  }
  if (!data.project || !data.project.id) {
    throw new Error('project.id が見つかりません。');
  }
  if (!Array.isArray(data.pages) || data.pages.length === 0) {
    throw new Error('pages が空です。');
  }
}

async function generateWireframes(data: WireDraft) {
  const warnings: string[] = [];
  const frames: string[] = [];
  const frameOrder = (Array.isArray(data.frames) && data.frames.length ? data.frames : DEFAULT_FRAME_ORDER).map((name) =>
    FRAME_PRESETS[name] ? name : 'Desktop'
  );

  const createdPages: PageNode[] = [];

  for (const pageSpec of data.pages) {
    const page = figma.createPage();
    page.name = `${data.project.title} / ${pageSpec.page_id}`;
    createdPages.push(page);

    let cursorX = 0;
    const spacing = 160;

    for (const frameKey of frameOrder) {
      const preset = FRAME_PRESETS[frameKey] ?? FRAME_PRESETS.Desktop;
      const frame = figma.createFrame();
      frame.name = `${pageSpec.page_id} | ${preset.name}`;
      configureFrame(frame, preset);
      frame.x = cursorX;
      frame.y = 0;
      cursorX += preset.width + spacing;

      page.appendChild(frame);
      frames.push(`${page.name} - ${frame.name}`);

      await populateSections(frame, pageSpec, warnings);

      if (pageSpec.notes && pageSpec.notes.length) {
        await insertNotes(frame, pageSpec.notes);
      }

      frame.setRelaunchData({ 'regenerate-wire': 'Regenerate this frame from Wire JSON' });
    }
  }

  if (createdPages.length) {
    figma.currentPage = createdPages[0];
  }

  return { warnings, frames };
}

function configureFrame(frame: FrameNode, preset: FramePreset) {
  frame.resizeWithoutConstraints(preset.width, preset.baseHeight);
  frame.layoutMode = 'VERTICAL';
  frame.primaryAxisSizingMode = 'AUTO';
  frame.counterAxisSizingMode = 'FIXED';
  frame.counterAxisAlignItems = 'CENTER';
  frame.itemSpacing = preset.sectionSpacing;
  frame.paddingTop = preset.padding.top;
  frame.paddingBottom = preset.padding.bottom;
  frame.paddingLeft = preset.padding.horizontal;
  frame.paddingRight = preset.padding.horizontal;
  frame.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];
  frame.strokes = [];
  frame.effects = [];
  frame.clipsContent = false;
  if (preset.layoutGrid) {
    frame.layoutGrids = [preset.layoutGrid];
  } else {
    frame.layoutGrids = [];
  }
}

async function populateSections(frame: FrameNode, page: WirePage, warnings: string[]) {
  for (const section of page.sections) {
    const instance = await createSectionInstance(section, warnings, page.page_id);
    frame.appendChild(instance);
    instance.layoutAlign = 'STRETCH';
    if (instance.type === 'FRAME' || instance.type === 'INSTANCE') {
      // Ensure Auto Layout children stretch properly
      if ('counterAxisSizingMode' in instance && instance.layoutMode === 'VERTICAL') {
        instance.counterAxisSizingMode = 'AUTO';
        instance.primaryAxisSizingMode = 'AUTO';
      }
    }
    if (section.placeholders && Object.keys(section.placeholders).length) {
      await applyPlaceholders(instance, section.placeholders, warnings, page.page_id);
    }
  }
}

async function createSectionInstance(section: WireSection, warnings: string[], pageId: string): Promise<SceneNode> {
  const componentName = `Section/${section.kind}/${section.variant}`;
  const component = findComponentByName(componentName);
  if (component) {
    const instance = component.createInstance();
    instance.name = componentName;
    return instance;
  }

  warnings.push(
    `[${pageId}] コンポーネント '${componentName}' が見つからなかったためプレースホルダーを配置しました。`
  );
  return buildPlaceholderSection(section);
}

function findComponentByName(name: string): ComponentNode | null {
  const node = figma.root.findOne((n) => n.type === 'COMPONENT' && n.name === name);
  return (node as ComponentNode) ?? null;
}

function buildPlaceholderSection(section: WireSection): FrameNode {
  const frame = figma.createFrame();
  frame.name = `Placeholder ${section.kind}/${section.variant}`;
  frame.layoutMode = 'VERTICAL';
  frame.primaryAxisSizingMode = 'AUTO';
  frame.counterAxisSizingMode = 'AUTO';
  frame.itemSpacing = 8;
  frame.paddingTop = 24;
  frame.paddingBottom = 24;
  frame.paddingLeft = 24;
  frame.paddingRight = 24;
  frame.strokes = [{ type: 'SOLID', color: { r: 0.87, g: 0.44, b: 0.2 } }];
  frame.dashPattern = [4, 4];
  frame.fills = [{ type: 'SOLID', color: { r: 1, g: 0.97, b: 0.92 }, opacity: 0.6 }];

  const title = figma.createText();
  title.name = 'placeholder-heading';
  void setText(title, `${section.kind}/${section.variant} 未対応`);

  const body = figma.createText();
  body.name = 'placeholder-body';
  void setText(
    body,
    'UI Kit に該当コンポーネントが存在しません。\nコンポーネントを追加するかマッピングを更新してください。'
  );

  frame.appendChild(title);
  frame.appendChild(body);

  return frame;
}

async function applyPlaceholders(node: SceneNode, placeholders: Record<string, string>, warnings: string[], pageId: string) {
  const textNodes = findAllTextNodes(node);
  const mapped = new Set<TextNode>();

  for (const [key, value] of Object.entries(placeholders)) {
    const target = findMatchingTextNode(textNodes, key);
    if (!target) {
      warnings.push(`[${pageId}] プレースホルダー '${key}' に対応するテキストレイヤーが見つかりませんでした。`);
      continue;
    }
    await setText(target, value);
    mapped.add(target);
  }

  if (textNodes.length && mapped.size === 0) {
    warnings.push(`[${pageId}] プレースホルダーを挿入できませんでした。レイヤー名を確認してください。`);
  }
}

function findAllTextNodes(root: SceneNode): TextNode[] {
  if ('findAll' in root) {
    return root.findAll((n): n is TextNode => n.type === 'TEXT');
  }
  return [];
}

function findMatchingTextNode(nodes: TextNode[], key: string): TextNode | undefined {
  const normalizedKey = normalize(key);
  return nodes.find((node) => normalize(node.name) === normalizedKey);
}

function normalize(input: string): string {
  return input.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
}

async function setText(node: TextNode, value: string) {
  const fontName = node.fontName;
  if (fontName === figma.mixed) {
    const ranges = node.getRangeAllFontNames(0, node.characters.length || 1);
    for (const rangeFont of ranges) {
      await figma.loadFontAsync(rangeFont);
    }
  } else {
    await figma.loadFontAsync(fontName as FontName);
  }
  node.characters = value;
}

async function insertNotes(frame: FrameNode, notes: string[]) {
  const noteFrame = figma.createFrame();
  noteFrame.name = 'Notes';
  noteFrame.layoutMode = 'VERTICAL';
  noteFrame.primaryAxisSizingMode = 'AUTO';
  noteFrame.counterAxisSizingMode = 'AUTO';
  noteFrame.itemSpacing = 4;
  noteFrame.paddingLeft = 0;
  noteFrame.paddingRight = 0;
  noteFrame.paddingTop = 16;
  noteFrame.paddingBottom = 0;
  noteFrame.fills = [];
  noteFrame.strokes = [];
  noteFrame.layoutAlign = 'STRETCH';

  const heading = figma.createText();
  heading.name = 'NoteHeading';
  await setText(heading, 'Notes');
  heading.fontSize = 14;

  const body = figma.createText();
  body.name = 'NoteBody';
  await setText(body, notes.map((n, idx) => `${idx + 1}. ${n}`).join('\n'));
  body.fontSize = 11;

  noteFrame.appendChild(heading);
  noteFrame.appendChild(body);
  frame.appendChild(noteFrame);
}

function pushStatus(message: string) {
  figma.ui.postMessage({ type: 'status', message });
}

function pushWarnings(items: string[]) {
  figma.ui.postMessage({ type: 'warnings', items });
}

function pushError(message: string) {
  figma.ui.postMessage({ type: 'error', message });
  figma.notify(`エラー: ${message}`, { error: true });
}
