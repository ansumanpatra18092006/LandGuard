// Several of the pointer-driven hooks (useSpotlight, useTilt, useMagnetic) each want to
// own a ref and a pair of pointer handlers on the same element. React only accepts one
// `ref` prop, so this merges any number of their prop objects into one: refs are called
// together, matching handlers are called together, and any data-* attributes pass through.
export function combineFX(...propsList) {
  const rest = Object.assign({}, ...propsList.map(({ ref, onPointerMove, onPointerLeave, ...keep }) => keep));
  return {
    ...rest,
    ref: node => { for (const props of propsList) setRef(props.ref, node); },
    onPointerMove: event => { for (const props of propsList) props.onPointerMove?.(event); },
    onPointerLeave: event => { for (const props of propsList) props.onPointerLeave?.(event); },
  };
}

function setRef(ref, node) {
  if (typeof ref === 'function') ref(node);
  else if (ref) ref.current = node;
}
