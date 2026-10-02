// Seth's dashboard — small touches only. No frameworks, no tracking.

// Fade sections in as they scroll into view.
(function () {
  const sections = document.querySelectorAll("section");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08 }
  );
  sections.forEach((s) => {
    s.classList.add("reveal");
    observer.observe(s);
  });
})();

// Brand easter egg: click "seth." in the nav for a console hello.
document.querySelector(".brand").addEventListener("click", (e) => {
  e.preventDefault();
  console.log("🎛️ TheArtfulDodger was here.");
  window.scrollTo({ top: 0, behavior: "smooth" });
});
