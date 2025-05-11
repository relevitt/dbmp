"use strict";

W.button = function (txt, click) {
  var bn = W.button.Button.cloneNode(true);
  bn.innerHTML = txt;
  // We have to recreate the <input> element, because setting bn.innerHTML
  // has the effect of deleting it. I think the <input> element exists to
  // allow tabbing through buttons
  var input = document.createElement("input");
  bn.appendChild(input);
  input.onfocus = function (e) {
    W.css.addClasses(e.target.parentNode, "button_focus");
  };
  input.onblur = function (e) {
    W.css.removeClasses(e.target.parentNode, "button_focus");
  };
  input.onkeydown = function (e) {
    if (e.keyCode == 13) e.target.parentNode.click();
  };
  bn.onclick = click;
  bn.focus = function (e) {
    this.querySelector("input").focus();
  }.bind(bn);
  return bn;
};

W.util.ready(function () {
  //element for cloning
  var div = document.querySelector("#W-button-for-cloning");
  W.button.Button = div.querySelector(".W-button");
  //now that we have it, remove it from the dom
  div.removeChild(W.button.Button);
  document.body.removeChild(div);
});
