class simple extends foundry.applications.api.HandlebarsApplicationMixin(foundry.applications.api.ApplicationV2) {
  static #customVideoCache;
  constructor(options) {
    simple.#injectCSS();
    document.body.classList.add("join-theme-simple");
    super(options);
    game.users.apps.push(this);
  }

  static #injectCSS() {
    const id = "simple-join-theme-style";
    if ( document.getElementById(id) ) return;
    const href = "joinmenu-so-nice/simple/custom.css";
    const preloadId = "simple-join-theme-preload";
    if ( !document.getElementById(preloadId) ) {
      const preload = document.createElement("link");
      preload.id = preloadId;
      preload.rel = "preload";
      preload.as = "style";
      preload.href = href;
      document.head.appendChild(preload);
    }
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.body.classList.add("join-theme-simple-loading");
    link.addEventListener("load", () => {
      document.body.classList.remove("join-theme-simple-loading");
      document.body.classList.add("join-theme-simple-ready");
    }, {once: true});
    document.head.appendChild(link);
  }

  static DEFAULT_OPTIONS = foundry.utils.mergeObject(super.DEFAULT_OPTIONS, {
    id: "join-game",
    window: {
      frame: false,
      positioned: false
    }
  }, {inplace: false});

  static PARTS = {
    hero: {
      id: "hero",
      template: "templates/joinmenu-so-nice/simple/simple-hero.hbs"
    },
    form: {
      id: "form",
      template: "templates/joinmenu-so-nice/simple/simple-form.hbs",
      forms: {
        "#join-game-form": {
          handler: simple.#onSubmitLoginForm
        }
      }
    },
    setup: {
      id: "setup",
      template: "templates/joinmenu-so-nice/simple/simple-setup.hbs",
      forms: {
        "#join-game-setup": {
          handler: simple.#onSubmitSetupForm
        }
      }
    }
  };

  async _prepareContext() {
    const stripHTML = foundry?.utils?.stripHTML ?? (s => s);
    const description = game.world?.description ? stripHTML(game.world.description) : "";
    const heroImage = game.world?.background ?? "";
    const heroVideo = await simple.#resolveHeroVideo(heroImage);
    return {
      isAdmin: game.data.isAdmin,
      users: game.users,
      world: game.world,
      passwordString: game.data.passwordString,
      usersCurrent: game.users.filter(u => u.active).length,
      usersMax: game.users.contents.length,
      simpleTheme: {
        tagline: description.slice(0, 120) || game.world?.title || "冒险从此刻开始",
        cta: game.world?.subtitle ?? "立即加入",
        heroImage,
        heroVideo
      }
    };
  }

  _syncPartState(partId, newElement, priorElement) {
    super._syncPartState(partId, newElement, priorElement);
    if ( (partId === "form") && priorElement ) {
      newElement.userid.value = priorElement.userid.value;
      if ( newElement.userid.selectedOptions[0]?.disabled ) newElement.userid.value = "";
      newElement.password.value = priorElement.password.value;
    }
  }

  static async #onSubmitSetupForm(event, form, formData) {
    event.preventDefault();
    form.disabled = true;

    const othersActive = game.users.filter(u => u.active).length;
    if ( othersActive ) {
      const warning = othersActive > 1 ? "GAME.ReturnSetupActiveUsers" : "GAME.ReturnSetupActiveUser";
      const confirm = await foundry.applications.api.DialogV2.confirm({
        window: {title: "GAME.ReturnSetup"},
        content: `<p>${game.i18n.format(warning, {number: othersActive})}</p>`
      });
      if ( !confirm ) {
        form.disabled = false;
        return;
      }
    }

    const postData = Object.assign(formData.object, {action: "shutdown"});
    return this.#post(form, postData);
  }

  static async #onSubmitLoginForm(event, form, formData) {
    event.preventDefault();
    if ( !formData.get("userid") ) return ui.notifications.error("JOIN.ErrorMustSelectUser", {localize: true});
    const postData = Object.assign(formData.object, {action: "join"});
    return this.#post(form, postData);
  }

  async #post(form, postData) {
    form.disabled = true;
    const joinURL = foundry.utils.getRoute("join");
    const user = game.users.get(postData.userid)?.name || postData.userid;
    let response;

    try {
      response = await foundry.utils.fetchJsonWithTimeout(joinURL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(postData)
      });
    }
    catch (error) {
      if ( error instanceof foundry.utils.HttpError ) {
        ui.notifications.error(error.displayMessage, {format: {user}});
      }
      else {
        ui.notifications.error(foundry.utils.escapeHTML(String(error)));
      }
      form.disabled = false;
      return;
    }

    ui.notifications.info(response.message, {format: {user}});
    setTimeout(() => window.location.href = response.redirect, 500);
  }

  async close(options = {}) {
    document.body.classList.remove("join-theme-simple", "join-theme-simple-ready", "join-theme-simple-loading");
    return super.close(options);
  }

  static async #resolveHeroVideo(heroImage) {
    const media = heroImage?.trim?.() ?? "";
    if ( media && /\.webm(\?.*)?$/i.test(media) ) return media;
    if ( typeof simple.#customVideoCache === "string" ) return simple.#customVideoCache;
    try {
      const response = await fetch("joinmenu-so-nice/simple/background.webm", {method: "HEAD"});
      simple.#customVideoCache = response.ok ? "joinmenu-so-nice/simple/background.webm" : "";
    }
    catch {
      simple.#customVideoCache = "";
    }
    return simple.#customVideoCache;
  }
}

return simple;
