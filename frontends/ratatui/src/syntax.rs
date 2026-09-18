//! Local, bounded syntax colour. Source/clipboard ownership stays with the caller.
use super::*;
use std::{cell::RefCell, collections::VecDeque, sync::OnceLock};
use syntect::{
    easy::HighlightLines,
    highlighting::{StyleModifier, Theme, ThemeItem},
    parsing::SyntaxSet,
};

pub const MAX_BYTES: usize = 16 * 1024;
const MAX_LINES: usize = 256;
const MAX_LINE_BYTES: usize = 1024;
const CACHE_ENTRIES: usize = 8;
type Cached = (String, String, Vec<Line<'static>>);
thread_local! {
    static CACHE: RefCell<VecDeque<Cached>> = const { RefCell::new(VecDeque::new()) };
}
static SYNTAXES: OnceLock<SyntaxSet> = OnceLock::new();
static THEME: OnceLock<Theme> = OnceLock::new();

fn theme() -> Theme {
    let colour = |value| match value {
        Color::Rgb(r, g, b) => syntect::highlighting::Color { r, g, b, a: 255 },
        _ => unreachable!("plain themes never initialize the syntax theme"),
    };
    let mut theme = Theme::default();
    theme.settings.foreground = Some(colour(palette().ink));
    theme.settings.background = Some(colour(palette().panel));
    for (scope, value) in [
        ("comment, punctuation.definition.comment", palette().muted),
        (
            "keyword, storage, entity.name, support.function",
            palette().green,
        ),
        ("string, constant, support.constant", palette().amber),
        ("invalid", palette().red),
    ] {
        theme.scopes.push(ThemeItem {
            scope: scope.parse().expect("static syntax selectors"),
            style: StyleModifier {
                foreground: Some(colour(value)),
                ..Default::default()
            },
        });
    }
    theme
}

pub fn plain(source: &str) -> Vec<Line<'static>> {
    source
        .split_terminator('\n')
        .map(|line| {
            Line::styled(
                line.to_owned(),
                Style::default().fg(palette().ink).bg(palette().panel),
            )
        })
        .collect()
}

fn token(language: &str) -> String {
    let name = language.split_whitespace().next().unwrap_or("");
    if name.len() > 64 {
        return String::new();
    }
    let name = name.to_ascii_lowercase();
    match name.as_str() {
        "sh" | "shell" | "console" => "bash".into(),
        "rs" => "rust".into(),
        "py" => "python".into(),
        "js" | "node" => "javascript".into(),
        "yml" => "yaml".into(),
        _ => name,
    }
}

/// Limits bound parser input, not a hard per-regex CPU deadline. Unsupported or
/// oversized blocks stay plain; no source is truncated to purchase colour.
pub fn eligible(source: &str) -> bool {
    source.len() <= MAX_BYTES
        && source.lines().take(MAX_LINES + 1).count() <= MAX_LINES
        && source.lines().all(|line| line.len() <= MAX_LINE_BYTES)
}

pub fn lines(source: &str, language: &str, budget: &mut usize) -> Vec<Line<'static>> {
    let language = token(language);
    if matches!(palette().syntax_theme, SyntaxTheme::Plain)
        || matches!(
            language.as_str(),
            "" | "text" | "txt" | "plaintext" | "indented"
        )
        || source.len() > *budget
        || !eligible(source)
    {
        return plain(source);
    }
    *budget -= source.len();
    if let Some(lines) = CACHE.with(|cache| {
        cache
            .borrow()
            .iter()
            .find(|(lang, text, _)| lang == &language && text == source)
            .map(|(_, _, lines)| lines.clone())
    }) {
        return lines;
    }
    let syntaxes = SYNTAXES.get_or_init(SyntaxSet::load_defaults_newlines);
    let Some(syntax) = syntaxes.find_syntax_by_token(&language) else {
        return plain(source);
    };
    let mut highlighter = HighlightLines::new(syntax, THEME.get_or_init(theme));
    let mut result = Vec::new();
    for line in source.split_inclusive('\n') {
        let Ok(tokens) = highlighter.highlight_line(line, syntaxes) else {
            return plain(source);
        };
        result.push(Line::from(
            tokens
                .into_iter()
                .filter_map(|(style, token)| {
                    let token = token.strip_suffix('\n').unwrap_or(token);
                    if token.is_empty() {
                        return None;
                    }
                    let colour = style.foreground;
                    Some(Span::styled(
                        token.to_owned(),
                        Style::default()
                            .fg(Color::Rgb(colour.r, colour.g, colour.b))
                            .bg(palette().panel),
                    ))
                })
                .collect::<Vec<_>>(),
        ));
    }
    CACHE.with(|cache| {
        let mut cache = cache.borrow_mut();
        if cache.len() == CACHE_ENTRIES {
            cache.pop_front();
        }
        cache.push_back((language, source.to_owned(), result.clone()));
    });
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn highlight(source: &str, language: &str) -> Vec<Line<'static>> {
        let mut budget = MAX_BYTES;
        lines(source, language, &mut budget)
    }

    #[test]
    fn languages_colour_tokens_without_changing_text() {
        for (language, source) in [
            ("python", "def greeting():\n    return \"Hello, 界\"\n"),
            ("rs", "fn main() { let x = \"界\"; }\n"),
            ("js", "const x = \"界\"; // comment\n"),
            ("sh", "echo \"Hello\" # comment\n"),
            ("json", "{\"hello\": 123}\n"),
        ] {
            let rows = highlight(source, language);
            assert_eq!(
                rows.iter()
                    .map(ToString::to_string)
                    .collect::<Vec<_>>()
                    .join("\n")
                    + "\n",
                source
            );
            let colours: std::collections::HashSet<_> = rows
                .iter()
                .flat_map(|r| &r.spans)
                .map(|s| s.style.fg)
                .collect();
            if !matches!(palette().syntax_theme, SyntaxTheme::Plain) {
                assert!(colours.len() > 1, "{language}");
                assert!(colours.iter().all(|c| {
                    [
                        palette().ink,
                        palette().muted,
                        palette().green,
                        palette().amber,
                        palette().red,
                    ]
                    .into_iter()
                    .any(|p| *c == Some(p))
                }));
            } else {
                assert_eq!(rows, plain(source));
            }
        }
    }

    #[test]
    fn fallback_limits_and_cache_keep_whitespace_and_content() {
        for (source, language, mut budget) in [
            ("  keep whitespace\n\n".into(), "unrecognized", MAX_BYTES),
            ("x".repeat(MAX_BYTES + 1), "python", MAX_BYTES),
            ("x".repeat(MAX_LINE_BYTES + 1), "python", MAX_BYTES),
            ("x\n".repeat(MAX_LINES + 1), "python", MAX_BYTES),
            ("print('hi')\n".into(), "python", 0),
        ] {
            assert_eq!(lines(&source, language, &mut budget), plain(&source));
        }
        for n in 0..CACHE_ENTRIES + 3 {
            let source = format!("value = {n}\n");
            let first = highlight(&source, "py");
            assert_eq!(first, highlight(&source, "python extra-info"));
        }
        CACHE.with(|cache| assert!(cache.borrow().len() <= CACHE_ENTRIES));
    }

    #[test]
    fn multiline_state_stays_inside_one_block() {
        let source = "value = \"\"\"first\nsecond\n\"\"\"\nreturn 123\n";
        let rows = highlight(source, "python");
        let second = rows[1].spans[0].style.fg;
        let standalone = highlight("second\n", "python");
        if !matches!(palette().syntax_theme, SyntaxTheme::Plain) {
            assert_ne!(second, standalone[0].spans[0].style.fg);
        }
        assert_eq!(rows[1].to_string(), "second");
    }
}
