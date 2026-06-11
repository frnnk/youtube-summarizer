"""Manual test for summary.py — needs an API key in .env (ANTHROPIC_API_KEY or
OPENAI_API_KEY). Run:  uv run test_summary.py
"""

from youtube_summarizer import summary, ui
from youtube_summarizer.settings import load_settings

TRANSCRIPT = """
Hey everyone, welcome back to the channel. Today we're talking about why most
people fail to build lasting habits, and what actually works instead. The first
mistake people make is relying on motivation. Motivation is great when you have
it, but it's unreliable. It comes and goes with your mood, the weather, how much
sleep you got. If your habit depends on feeling motivated, it will collapse the
first bad week you have.

The second idea is to make the habit ridiculously small. Most people set goals
that are way too ambitious. They decide they'll go to the gym for an hour every
single day, and they burn out in a week. Instead, shrink the habit until it feels
almost embarrassingly easy. Do one push-up. Read one page. Meditate for sixty
seconds. The point isn't the workout, it's casting a vote for the kind of person
you want to become. Once the habit is established, scaling it up is easy.

The third principle is environment design. We dramatically overestimate willpower
and underestimate our surroundings. If junk food is on the counter, you'll eat it.
If your phone is across the room while you work, you'll check it less. Don't try to
resist temptation with brute force. Remove the temptation, or add friction. Make
the good behavior the path of least resistance and the bad behavior annoying.

The fourth point is habit stacking. Attach a new habit to something you already do
automatically. After I pour my morning coffee, I write down three priorities for
the day. The existing habit becomes the trigger for the new one, so you don't have
to remember anything. Your brain already runs the first action on autopilot, and
the new action rides along with it.

Finally, track your progress, but keep it simple. A calendar where you mark an X
for each day you complete the habit is enough. The chain of X's becomes its own
motivation, because you don't want to break the streak. But here's the key rule:
never miss twice. Missing one day is an accident. Missing two days is the start of
a new, worse habit. So if you slip, just get back on track the very next day.

To recap: forget motivation, shrink the habit, design your environment, stack new
habits onto old ones, and never miss twice. Do those five things and the habit
basically builds itself. Thanks for watching, and I'll see you in the next one.
"""


def run(label: str, settings) -> None:
    print(f"\n===== {label} (chunk_chars={settings.chunk_chars}, "
          f"model={settings.model}) =====")
    result = summary.summarize(
        TRANSCRIPT.strip(), settings, on_progress=ui.progress_callback
    )
    ui.show_summary(result, title=label)


if __name__ == "__main__":
    print(f"transcript length: {len(TRANSCRIPT.strip())} chars")

    # 1) whole transcript in one prompt
    s = load_settings()
    run("Stuff path", s)

    # 2) Map-reduce path, force chunking by lowering the threshold
    s2 = load_settings()
    s2.chunk_chars = 800  # smaller than the transcript -> LangGraph map-reduce
    run("Map-reduce path", s2)
