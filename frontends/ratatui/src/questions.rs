//! Local answers remain separate from the composer and from approval decisions.
use super::*;
use interaction::Choice;
use std::collections::BTreeMap;

#[derive(Default)]
pub struct Questions {
    pub pending: BTreeMap<String, Value>,
    pub answers: BTreeMap<String, BTreeMap<String, Value>>,
}

fn choice(label: impl Into<String>, action: Action, detail: impl Into<String>) -> Choice {
    Choice {
        label: label.into(),
        action,
        detail: detail.into(),
    }
}

impl App {
    pub fn question_open(&mut self, id: String) {
        if let Some(row) = self.questions.pending.get(&id) {
            if row["questions"].as_array().is_some_and(|q| q.len() == 1) {
                self.question_edit(id.clone(), string(&row["questions"][0], "id"));
            } else {
                self.question_group(id);
            }
        }
    }
    pub fn question_list(&mut self) {
        let mut choices: Vec<_> = self
            .questions
            .pending
            .iter()
            .map(|(id, row)| {
                choice(
                    format!(
                        "Answer · {}",
                        safe(&string(&row["questions"][0], "question"))
                    ),
                    Action::QuestionGroup(id.clone()),
                    "Local answers are not sent until you choose Submit reviewed answers.",
                )
            })
            .collect();
        choices.extend(
            self.items
                .iter()
                .rev()
                .filter(|i| i.kind == "question" && i.status != "waiting")
                .take(100)
                .map(|i| {
                    choice(
                        format!(
                            "{} · {}",
                            i.status,
                            safe(
                                &i.text
                                    .lines()
                                    .nth(1)
                                    .unwrap_or("")
                                    .chars()
                                    .take(100)
                                    .collect::<String>()
                            )
                        ),
                        Action::Message(i.id.clone()),
                        "Retained question and outcome; open to inspect or copy.",
                    )
                }),
        );
        self.menu("Questions · clarification, never permission", choices);
        self.ui.menu.as_mut().unwrap().detail = "Escape dismisses without answering. Unsent choices survive dismissal while the request is live, but are not crash-durable. Stop cancels unanswered questions. Arrivals never take composer focus.".into();
    }

    pub fn question_group(&mut self, id: String) {
        let Some(row) = self.questions.pending.get(&id) else {
            self.status = "Question is no longer waiting; no answer sent".into();
            return;
        };
        let rows = row["questions"].as_array().cloned().unwrap_or_default();
        let answers = self.questions.answers.get(&id);
        let mut detail = String::from(
            "Review all answers before submitting. This does not grant tool permission.\n",
        );
        let mut choices = Vec::new();
        for question in &rows {
            let qid = string(question, "id");
            let answer = answers.and_then(|a| a.get(&qid));
            let summary = answer
                .map(|a| {
                    if a["option"].is_string() {
                        string(a, "option")
                    } else {
                        string(a, "text")
                    }
                })
                .unwrap_or_else(|| "Unanswered".into());
            detail.push_str(&format!(
                "\n{}\nAnswer: {}\n",
                safe(&string(question, "question")),
                safe(&summary)
            ));
            choices.push(choice(
                format!(
                    "{} · {}",
                    if answer.is_some() {
                        "Edit answer"
                    } else {
                        "Answer"
                    },
                    safe(&string(question, "question"))
                ),
                Action::QuestionEdit(id.clone(), qid),
                "",
            ));
        }
        if rows
            .iter()
            .all(|q| answers.is_some_and(|a| a.contains_key(&string(q, "id"))))
        {
            choices.push(choice(
                "Submit reviewed answers",
                Action::QuestionSubmit(id.clone()),
                "",
            ));
        }
        choices.push(choice(
            "Cancel this question request (send no answers)",
            Action::QuestionCancel(id),
            "",
        ));
        self.menu("Questions · review answers", choices);
        self.ui.menu.as_mut().unwrap().detail = detail;
    }

    pub fn question_edit(&mut self, id: String, qid: String) {
        let Some(q) = self
            .questions
            .pending
            .get(&id)
            .and_then(|v| v["questions"].as_array())
            .and_then(|qs| qs.iter().find(|q| q["id"] == qid))
        else {
            return;
        };
        let detail = safe(&string(q, "question"));
        let mut choices: Vec<_> = q["options"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|o| {
                choice(
                    safe(&string(o, "label")),
                    Action::QuestionChoice(id.clone(), qid.clone(), string(o, "label")),
                    format!(
                        "{}\n{}\nSelection is local; review before submitting.",
                        detail,
                        safe(&string(o, "description"))
                    ),
                )
            })
            .collect();
        choices.push(choice(
            "Write my own answer",
            Action::QuestionText(id, qid),
            detail.clone(),
        ));
        self.menu("Question · choose or write your own answer", choices);
        self.ui.menu.as_mut().unwrap().detail = detail;
    }

    pub fn question_text(&mut self, id: String, qid: String) {
        let text = self
            .questions
            .answers
            .get(&id)
            .and_then(|a| a.get(&qid))
            .map(|a| string(a, "text"))
            .unwrap_or_default();
        self.prompt("Answer question");
        let prompt = self.flow.prompt.as_mut().unwrap();
        prompt.identity = Some(id.clone());
        prompt.question = Some((id, qid));
        prompt.editor.insert_str(text);
    }

    pub fn save_question_text(&mut self, id: String, qid: String, text: String) {
        if self.questions.pending.contains_key(&id) {
            if !text.trim().is_empty() {
                self.questions
                    .answers
                    .entry(id.clone())
                    .or_default()
                    .insert(qid, json!({"option":null,"text":text}));
            } else if let Some(answers) = self.questions.answers.get_mut(&id) {
                answers.remove(&qid);
            }
            self.question_group(id);
        }
    }
}
