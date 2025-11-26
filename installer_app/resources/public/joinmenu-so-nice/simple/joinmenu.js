class willowShore extends foundry.applications.api.HandlebarsApplicationMixin(foundry.applications.api.ApplicationV2) {
  static #customVideoCache;
  
  constructor(options) {
    willowShore.#injectCSS();
    document.body.classList.add("join-theme-willow-shore");
    super(options);
    game.users.apps.push(this);
  }

  static #injectCSS() {
    const id = "willow-shore-join-theme-style";
    if ( document.getElementById(id) ) return;
    
    // 路径指向：modules/joinmenu-so-nice/willow-shore/custom.css
    const href = "modules/joinmenu-so-nice/willow-shore/custom.css";
    
    const preloadId = "willow-shore-join-theme-preload";
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
    document.body.classList.add("join-theme-willow-shore-loading");
    link.addEventListener("load", () => {
      document.body.classList.remove("join-theme-willow-shore-loading");
      document.body.classList.add("join-theme-willow-shore-ready");
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
      template: "modules/joinmenu-so-nice/willow-shore/willow-hero.hbs"
    },
    form: {
      id: "form",
      template: "modules/joinmenu-so-nice/willow-shore/willow-form.hbs",
      forms: {
        "#join-game-form": {
          handler: willowShore.#onSubmitLoginForm
        }
      }
    },
    setup: {
      id: "setup",
      template: "modules/joinmenu-so-nice/willow-shore/willow-setup.hbs",
      forms: {
        "#join-game-setup": {
          handler: willowShore.#onSubmitSetupForm
        }
      }
    }
  };

  async _prepareContext() {
    const stripHTML = foundry?.utils?.stripHTML ?? (s => s);
    const description = game.world?.description ? stripHTML(game.world.description) : "";
    const heroImage = game.world?.background ?? "";
    const heroVideo = await willowShore.#resolveHeroVideo(heroImage);
    
    return {
      isAdmin: game.data.isAdmin,
      users: game.users,
      world: game.world,
      passwordString: game.data.passwordString,
      usersCurrent: game.users.filter(u => u.active).length,
      usersMax: game.users.contents.length,
      // 数据对象名保持 simpleTheme 以方便模板调用，内容定制化
      simpleTheme: {
        tagline: description.slice(0, 120) || "戴上纸面具，欺瞒林中灵。",
        cta: game.world?.subtitle ?? "加入祭典",
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
    document.body.classList.remove("join-theme-willow-shore", "join-theme-willow-shore-ready", "join-theme-willow-shore-loading");
    return super.close(options);
  }

  static async #resolveHeroVideo(heroImage) {
    const media = heroImage?.trim?.() ?? "";
    if ( media && /\.webm(\?.*)?$/i.test(media) ) return media;
    if ( typeof willowShore.#customVideoCache === "string" ) return willowShore.#customVideoCache;
    try {
      // 路径指向：modules/joinmenu-so-nice/willow-shore/background.webm
      const videoPath = "modules/joinmenu-so-nice/willow-shore/background.webm";
      const response = await fetch(videoPath, {method: "HEAD"});
      willowShore.#customVideoCache = response.ok ? videoPath : "";
    }
    catch {
      willowShore.#customVideoCache = "";
    }
    return willowShore.#customVideoCache;
  }
}

return willowShore;