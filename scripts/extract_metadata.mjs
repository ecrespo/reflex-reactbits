import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const ROOT = process.argv[2];
const OUT = process.argv[3];
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const { componentMetadata } = await import(path.join(ROOT, 'src/constants/Information.js'));
const IMPLEMENTATIONS = { Antigravity: 'AntigravityInner', GradualBlur: 'DEFAULT_CONFIG' };

const walk = (node, visit) => { visit(node); ts.forEachChild(node, c => walk(c, visit)); };

function parse(file) {
  const ast = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
  const decls = new Map();
  for (const st of ast.statements) {
    let s = st;
    if (ts.isVariableStatement(s)) for (const d of s.declarationList.declarations) { if (ts.isIdentifier(d.name)) decls.set(d.name.text, d.initializer); }
    else if (ts.isFunctionDeclaration(s) && s.name) decls.set(s.name.text, s);
  }
  return { ast, decls };
}
function unwrap(node, decls, seen = new Set()) {
  if (!node) return undefined;
  if (ts.isIdentifier(node) && !seen.has(node.text)) return unwrap(decls.get(node.text), decls, new Set([...seen, node.text]));
  if (ts.isCallExpression(node) && /^(React\.)?(memo|forwardRef)$/.test(node.expression.getText())) return unwrap(node.arguments[0], decls, seen);
  if (ts.isParenthesizedExpression(node)) return unwrap(node.expression, decls, seen);
  return node;
}
function scalar(node, decls, seen = new Set()) {
  if (!node) return undefined;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isNumericLiteral(node)) return Number(node.text);
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.MinusToken) {
    const v = scalar(node.operand, decls, seen); return typeof v === 'number' ? -v : undefined;
  }
  if (ts.isIdentifier(node) && !seen.has(node.text)) return scalar(decls.get(node.text), decls, new Set([...seen, node.text]));
  return undefined;
}
function kindOf(node, decls, seen = new Set()) {
  if (!node) return null;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateExpression(node)) return 'str';
  if (ts.isNumericLiteral(node)) return 'number';
  if (ts.isPrefixUnaryExpression(node)) return kindOf(node.operand, decls, seen);
  if (node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword) return 'bool';
  if (ts.isArrayLiteralExpression(node)) return 'list';
  if (ts.isObjectLiteralExpression(node)) return 'dict';
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) return 'function';
  if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node) || ts.isJsxFragment(node)) return 'node';
  if (node.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(node) && node.text === 'undefined')) return null;
  if (ts.isIdentifier(node) && !seen.has(node.text)) return kindOf(decls.get(node.text), decls, new Set([...seen, node.text]));
  if (ts.isBinaryExpression(node)) return kindOf(node.left, decls, seen);
  return null;
}
function sourceProps(file, name) {
  const { ast, decls } = parse(file);
  let impl = unwrap(decls.get(IMPLEMENTATIONS[name] || name), decls);
  const props = [];
  let rest = false, hasChildren = false;
  if (impl && ts.isObjectLiteralExpression(impl)) {
    for (const p of impl.properties) if (ts.isPropertyAssignment(p)) props.push({ name: p.name.getText(), default: scalar(p.initializer, decls), defaultText: p.initializer.getText(), kind: kindOf(p.initializer, decls) });
    // GradualBlur also accepts extra props
    const main = unwrap(decls.get(name), decls);
    return { props, rest: true, hasChildren: false };
  }
  const param = impl?.parameters?.[0];
  let binding = param?.name;
  if (binding && ts.isIdentifier(binding)) {
    const propsName = binding.text; binding = undefined;
    walk(impl.body, n => {
      if (ts.isVariableDeclaration(n) && ts.isObjectBindingPattern(n.name) && n.initializer?.getText() === propsName) binding = n.name;
    });
  }
  if (binding && ts.isObjectBindingPattern(binding)) {
    for (const el of binding.elements) {
      if (el.dotDotDotToken) { rest = true; continue; }
      const key = (el.propertyName || el.name).getText();
      if (key === 'children') { hasChildren = true; continue; }
      props.push({ name: key, default: scalar(el.initializer, decls), defaultText: el.initializer?.getText() ?? null, kind: kindOf(el.initializer, decls) });
    }
  }
  return { props, rest, hasChildren, ast };
}
function callSites(files, propNames) {
  const res = {};
  for (const f of files) {
    const { ast } = parse(f);
    const refs = {};
    walk(ast, n => {
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && ts.isCallExpression(n.initializer)
          && /useRef$/.test(n.initializer.expression.getText()) && n.initializer.arguments[0] && ts.isIdentifier(n.initializer.arguments[0])
          && propNames.includes(n.initializer.arguments[0].text)) refs[n.name.text] = n.initializer.arguments[0].text;
    });
    walk(ast, n => {
      if (ts.isCallExpression(n)) {
        const t = n.expression.getText().replace(/\?\.$/, '').replace(/\?\./g, '.');
        let hit = null;
        for (const p of propNames) {
          if (t === p || t.endsWith('.' + p)) hit = p;
        }
        const m = t.match(/^(\w+)\.current$/);
        if (!hit && m && refs[m[1]]) hit = refs[m[1]];
        if (hit) (res[hit] ||= []).push(n.arguments.map(a => a.getText()));
      }
      if (ts.isJsxAttribute(n) && n.initializer && ts.isJsxExpression(n.initializer) && n.initializer.expression && ts.isIdentifier(n.initializer.expression)) {
        const v = n.initializer.expression.text;
        if (propNames.includes(v)) (res[v] ||= []).push(['<jsx:' + n.name.getText() + '>']);
      }
    });
  }
  return res;
}
function propTable(file) {
  if (!fs.existsSync(file)) return null;
  const { ast, decls } = parse(file);
  let init;
  walk(ast, n => { if (ts.isVariableDeclaration(n) && n.name.getText(ast) === 'propData') init = n.initializer; });
  if (!init) return null;
  if (ts.isCallExpression(init) && init.expression.getText(ast) === 'useMemo') {
    init = init.arguments[0]?.body;
    if (init && ts.isBlock(init)) init = init.statements.find(ts.isReturnStatement)?.expression;
  }
  if (init && ts.isParenthesizedExpression(init)) init = init.expression;
  if (!init || !ts.isArrayLiteralExpression(init)) return null;
  return init.elements.flatMap(row => {
    if (!ts.isObjectLiteralExpression(row)) return [];
    const f = new Map(row.properties.filter(ts.isPropertyAssignment).map(p => [p.name.getText(), p.initializer]));
    const get = k => { const v = scalar(f.get(k), decls); return v === undefined ? f.get(k)?.getText() : v; };
    return [{ name: get('name'), type: get('type'), default: get('default'), description: get('description') }];
  });
}
function demoDeps(file) {
  if (!fs.existsSync(file)) return null;
  const m = fs.readFileSync(file, 'utf8').match(/dependencyList=\{\[([^\]]*)\]\}/);
  return m ? [...m[1].matchAll(/['"]([^'"]+)['"]/g)].map(x => x[1]) : null;
}
function imports(file) {
  const { ast } = parse(file);
  const out = [];
  for (const st of ast.statements) if (ts.isImportDeclaration(st)) out.push(st.moduleSpecifier.text);
  return out;
}
const pkgName = s => s.startsWith('@') ? s.split('/').slice(0, 2).join('/') : s.split('/')[0];
// Pin the exact versions React Bits itself is locked to (package-lock.json).
const lock = JSON.parse(fs.readFileSync(path.join(ROOT, 'package-lock.json'), 'utf8'));
const allDeps = Object.fromEntries(Object.keys(pkg.dependencies).map(n => [n, lock.packages?.[`node_modules/${n}`]?.version || pkg.dependencies[n]]));

const out = [];
for (const [key, meta] of Object.entries(componentMetadata)) {
  const cat = key.split('/')[0]; const name = meta.name;
  const dir = path.join(ROOT, 'src/content', cat, name);
  if (!fs.existsSync(dir)) { console.error('no dir', key); continue; }
  const files = fs.readdirSync(dir).sort();
  const main = path.join(dir, `${name}.jsx`);
  const src = fs.readFileSync(main, 'utf8');
  const isDefault = new RegExp(`export default (function )?${name}\\b|export default ${name}Memo`).test(src);
  const sp = sourceProps(main, name);
  const codeFiles = files.filter(f => /\.(jsx?|tsx?)$/.test(f)).map(f => path.join(dir, f));
  const npm = new Set();
  for (const f of codeFiles) for (const i of imports(f)) if (!i.startsWith('.') && !['react', 'react-dom'].includes(pkgName(i))) npm.add(pkgName(i));
  const table = propTable(path.join(ROOT, 'src/demo', cat, `${name}Demo.jsx`));
  const names = [...new Set([...sp.props.map(p => p.name), ...(table || []).map(r => r.name)])];
  const events = names.filter(n => /^on[A-Z]/.test(n));
  out.push({
    key, category: cat, name, description: meta.description, docsUrl: meta.docsUrl, tags: meta.tags,
    files, isDefault, rest: sp.rest, hasChildren: sp.hasChildren || src.includes('children'),
    sourceProps: sp.props, table, npm: [...npm].sort().map(n => ({ name: n, version: allDeps[n] || null })),
    demoDeps: demoDeps(path.join(ROOT, 'src/demo', cat, `${name}Demo.jsx`)),
    calls: callSites(codeFiles, events)
  });
}
fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
console.log('components', out.length);

// ---------------------------------------------------------------------------
// Usage examples: turn the JSX usage snippet of each component's docs into a
// JSON description of props/children that the demo app can render.
const JSX = { $jsx: true };
function evalNode(node, decls, depth = 0) {
  if (!node || depth > 20) return undefined;
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)) return evalNode(node.expression, decls, depth + 1);
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isNumericLiteral(node)) return Number(node.text);
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (node.kind === ts.SyntaxKind.NullKeyword) return null;
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.MinusToken) {
    const v = evalNode(node.operand, decls, depth + 1); return typeof v === 'number' ? -v : undefined;
  }
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.AsteriskToken) {
    const a = evalNode(node.left, decls, depth + 1), b = evalNode(node.right, decls, depth + 1);
    return typeof a === 'number' && typeof b === 'number' ? a * b : undefined;
  }
  if (ts.isArrayLiteralExpression(node)) {
    const out = node.elements.map(e => evalNode(e, decls, depth + 1));
    return out.some(v => v === undefined) ? out.filter(v => v !== undefined) : out;
  }
  if (ts.isObjectLiteralExpression(node)) {
    const out = {};
    for (const p of node.properties) {
      if (ts.isPropertyAssignment(p)) {
        const v = evalNode(p.initializer, decls, depth + 1);
        if (v !== undefined) out[p.name.getText().replace(/^['"]|['"]$/g, '')] = v;
      } else if (ts.isShorthandPropertyAssignment(p)) {
        const v = evalNode(p.name, decls, depth + 1);
        if (v !== undefined) out[p.name.text] = v;
      }
    }
    return out;
  }
  if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node) || ts.isJsxFragment(node)) {
    const text = node.getText().replace(/\s+/g, ' ');
    const inner = ts.isJsxElement(node) ? node.children.map(c => (ts.isJsxText(c) ? c.getText() : '')).join('').trim() : '';
    return { $jsx: text.slice(0, 80), text: inner };
  }
  if (ts.isIdentifier(node) && decls.has(node.text)) return evalNode(decls.get(node.text), decls, depth + 1);
  return undefined;
}
function usageExample(usage, name) {
  if (!usage) return null;
  const ast = ts.createSourceFile('u.tsx', usage, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const decls = new Map();
  walk(ast, n => { if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer) decls.set(n.name.text, n.initializer); });
  let el = null;
  walk(ast, n => {
    if (el) return;
    if ((ts.isJsxSelfClosingElement(n) && n.tagName.getText() === name) || (ts.isJsxElement(n) && n.openingElement.tagName.getText() === name)) el = n;
  });
  if (!el) return null;
  const opening = ts.isJsxElement(el) ? el.openingElement : el;
  const props = {};
  for (const a of opening.attributes.properties) {
    if (!ts.isJsxAttribute(a)) continue;
    const key = a.name.getText();
    if (!a.initializer) { props[key] = true; continue; }
    const v = ts.isStringLiteral(a.initializer) ? a.initializer.text : evalNode(a.initializer.expression, decls);
    if (v !== undefined) props[key] = v;
  }
  let children = null;
  if (ts.isJsxElement(el)) {
    const kids = el.children.filter(c => !(ts.isJsxText(c) && !c.getText().trim()));
    children = kids.map(c => ts.isJsxText(c) ? c.getText().trim().replace(/\s+/g, ' ') : evalNode(ts.isJsxExpression(c) ? c.expression : c, decls) ?? { $jsx: c.getText().slice(0, 80) });
  }
  return { props, children };
}
const codeDir = path.join(ROOT, 'src/constants/code');
for (const c of out) {
  const dir = path.join(codeDir, c.category);
  const base = c.name.charAt(0).toLowerCase() + c.name.slice(1);
  const candidates = fs.readdirSync(dir).filter(f => f.toLowerCase() === `${base.toLowerCase()}code.js`);
  if (!candidates.length) { c.example = null; continue; }
  const text = fs.readFileSync(path.join(dir, candidates[0]), 'utf8');
  const m = text.match(/usage:\s*`([\s\S]*?)`,\s*\n/);
  try { c.example = usageExample(m ? m[1].replace(/\\`/g, '`') : null, c.name); } catch (e) { c.example = null; }
}
fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
console.log('examples', out.filter(c => c.example).length);
