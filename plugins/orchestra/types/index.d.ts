/** Value shapes stored through `$.state` by the Orchestra mods module. */
export interface PluginState {
  /** Session ids whose liveness marker this process wrote. */
  markers?: readonly string[];
}
