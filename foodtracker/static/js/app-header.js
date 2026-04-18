document.addEventListener("DOMContentLoaded", () => {
  const desktopBreakpoint = 767;
  const menus = document.querySelectorAll("[data-mobile-menu]");

  function closeMenu(menu) {
    const toggle = menu.parentElement.querySelector("[data-mobile-menu-toggle]");
    menu.classList.remove("is-open");
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
    }
  }

  menus.forEach((menu) => {
    const toggle = menu.parentElement.querySelector("[data-mobile-menu-toggle]");
    if (!toggle) {
      return;
    }

    toggle.addEventListener("click", () => {
      const isOpen = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    menu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (window.innerWidth <= desktopBreakpoint) {
          closeMenu(menu);
        }
      });
    });
  });

  document.addEventListener("click", (event) => {
    menus.forEach((menu) => {
      const toggle = menu.parentElement.querySelector("[data-mobile-menu-toggle]");
      if (!toggle) {
        return;
      }

      if (!menu.contains(event.target) && !toggle.contains(event.target)) {
        closeMenu(menu);
      }
    });
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > desktopBreakpoint) {
      menus.forEach(closeMenu);
    }
  });
});
