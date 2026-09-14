//! Bounded explicit discovery; copied code is a snapshot, never an executable action.
use super::*;
use interaction::Choice;
use pulldown_cmark::{CodeBlockKind, Event as Md, Parser, Tag, TagEnd};

#[derive(Debug, PartialEq)]
pub struct CodeBlock {
    pub message: String,
    pub ordinal: usize,
    pub language: String,
    pub content: String,
}

pub fn extract(source: &str, message: &str, limit: usize) -> (Vec<Arc<CodeBlock>>, bool) {
    let mut blocks = Vec::new();
    let mut current = None;
    for event in Parser::new(source) {
        match event {
            Md::Start(Tag::CodeBlock(kind)) => {
                if blocks.len() == limit {
                    return (blocks, true);
                }
                current = Some(CodeBlock {
                    message: message.into(),
                    ordinal: blocks.len() + 1,
                    language: match kind {
                        CodeBlockKind::Fenced(language) => language.to_string(),
                        _ => "indented".into(),
                    },
                    content: String::new(),
                });
            }
            Md::Text(text) => {
                if let Some(block) = &mut current {
                    block.content.push_str(&text);
                }
            }
            Md::End(TagEnd::CodeBlock) => {
                if let Some(block) = current.take() {
                    blocks.push(Arc::new(block));
                }
            }
            _ => (),
        }
    }
    (blocks, false)
}

impl App {
    pub fn code_blocks(&mut self) {
        let mut choices = Vec::new();
        let mut budget = 16 * 1024 * 1024;
        let mut partial = false;
        for item in self.items.iter().rev().filter(|i| i.kind == "assistant") {
            if item.text.len() > budget || choices.len() >= 100 {
                partial = true;
                break;
            }
            budget -= item.text.len();
            let (blocks, limited) = extract(&item.text, &item.id, 100 - choices.len());
            partial |= limited;
            choices.extend(blocks.into_iter().map(|block| Choice {
                label: format!(
                        "{} · block {} · {}",
                        if block.language.is_empty() {
                            "code".into()
                        } else {
                            safe(&block.language).chars().take(80).collect::<String>()
                        },
                        block.ordinal,
                        safe(block.content.lines().next().unwrap_or("(empty)"))
                            .chars()
                            .take(80)
                            .collect::<String>()
                    ),
                action: Action::CodeBlock(block),
                detail: String::new(),
            }));
        }
        self.menu("Code blocks · inspect / copy snapshots", choices);
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{}\nCode content excludes Markdown fences/indentation. No execution, file writes or model calls. Captured text may still be growing; reopen this catalog to refresh.",
            if partial {
                "Partial catalog: up to 100 blocks / 16 MiB recent assistant source."
            } else {
                "Assistant code blocks in retained source; newest messages first."
            }
        );
    }

    pub fn code_block(&mut self, block: Arc<CodeBlock>) {
        let mut choices = vec![Choice {
            label: "Go to source message".into(),
            action: Action::Jump(block.message.clone()),
            detail: String::new(),
        }];
        if block.content.len() <= 1024 * 1024 {
            choices.insert(
                0,
                Choice {
                    label: "Copy code content (without Markdown fences)".into(),
                    action: Action::CopyCode(block.clone()),
                    detail: String::new(),
                },
            );
        }
        choices.push(Choice {
            label: "Refresh code-block catalog".into(),
            action: Action::CodeBlocks,
            detail: String::new(),
        });
        self.menu("Code block · captured source · never executed", choices);
        self.ui.menu.as_mut().unwrap().detail = format!(
            "Message: {} · block {} · {}\nSnapshot preview: up to 12000 characters. {}\n\n{}",
            safe(&block.message),
            block.ordinal,
            safe(&block.language).chars().take(80).collect::<String>(),
            if block.content.len() > 1024 * 1024 {
                "Copy unavailable: content exceeds 1 MiB."
            } else {
                "Copy preserves the full parsed code content, including whitespace."
            },
            safe(&block.content.chars().take(12000).collect::<String>())
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn code_extraction_keeps_whitespace_unicode_and_never_html() {
        let (blocks, limited) = extract(
            "```python\n  print('界')\n\n```\n<script>bad()</script>\n\n~~~sh\necho hi\n~~~",
            "source-1",
            100,
        );
        assert!(!limited);
        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0].content, "  print('界')\n\n");
        assert_eq!(blocks[1].language, "sh");
        assert_eq!(blocks[1].ordinal, 2);
        assert_eq!(blocks[1].message, "source-1");
    }
    #[test]
    fn code_snapshots_do_not_retarget_partial_streams_and_have_bounds() {
        let mut source = "```text\nfirst".to_string();
        let (blocks, _) = extract(&source, "stream", 1);
        let before = blocks[0].content.clone();
        source.push_str(" later\n```\n\n```text\nsecond\n```");
        assert_eq!(blocks[0].content, before);
        let (new, limited) = extract(&source, "stream", 1);
        assert!(limited);
        assert_ne!(new[0].content, before);
    }
}
