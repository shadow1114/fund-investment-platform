import { useClickOutside } from "@mantine/hooks";
import { CheckSquare, ChevronDown, Square, X } from "lucide-react";
import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import styles from "./DataIngestion.module.css";

export type PickerOption = {
  id: string;
  code: string;
  name: string;
  tags?: string[];
  meta?: string;
};

export type SourceFilter = { value: string; label: string; count?: number };

type Props = {
  label: ReactNode;
  placeholder: string;
  query: string;
  onQueryChange: (value: string) => void;
  options: PickerOption[];
  selected: PickerOption[];
  onChange: (next: PickerOption[]) => void;
  loading?: boolean;
  error?: ReactNode;
  emptyText: string;
  total?: number;
  maxSelected?: number;
  disabled?: boolean;
  sources?: SourceFilter[];
  source?: string;
  onSourceChange?: (value: string) => void;
  footer?: ReactNode;
};

/** 可多选的模糊检索下拉；选中项以标签展示，筛选结果可一键全选。 */
export const TargetPicker = ({
  label,
  placeholder,
  query,
  onQueryChange,
  options,
  selected,
  onChange,
  loading = false,
  error,
  emptyText,
  total,
  maxSelected,
  disabled = false,
  sources,
  source,
  onSourceChange,
  footer,
}: Props) => {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const ref = useClickOutside(() => setOpen(false));
  const id = useId();
  const listId = `${id}-list`;
  const selectedIds = new Set(selected.map((item) => item.id));
  const full = maxSelected !== undefined && selected.length >= maxSelected;

  const toggle = (option: PickerOption) => {
    if (selectedIds.has(option.id))
      onChange(selected.filter((item) => item.id !== option.id));
    else if (!full) onChange([...selected, option]);
  };
  const selectAll = () => {
    const additions = options.filter((option) => !selectedIds.has(option.id));
    const room =
      maxSelected === undefined
        ? additions.length
        : maxSelected - selected.length;
    onChange([...selected, ...additions.slice(0, Math.max(0, room))]);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") setOpen(false);
    else if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((value) => Math.min(value + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && open && options[active]) {
      event.preventDefault();
      toggle(options[active]);
    } else if (event.key === "Backspace" && !query && selected.length)
      onChange(selected.slice(0, -1));
  };

  return (
    <div className={styles.picker} ref={ref}>
      <div className={styles.labelRow}>
        <span className={styles.fieldLabel} id={`${id}-label`}>
          {label} <span className={styles.required}>*</span>
        </span>
        <button
          type="button"
          className={styles.linkButton}
          onClick={() => onChange([])}
          disabled={disabled || selected.length === 0}
        >
          清空已选
        </button>
      </div>
      <div
        className={styles.pickerBox}
        data-disabled={disabled}
        onClick={() => !disabled && setOpen(true)}
      >
        {selected.map((item) => (
          <span key={item.id} className={styles.chip}>
            <span className={styles.chipCode}>{item.code}</span>
            <span className={styles.chipName} title={item.name}>
              {item.name}
            </span>
            <button
              type="button"
              className={styles.chipRemove}
              aria-label={`移除 ${item.code} ${item.name}`}
              disabled={disabled}
              onClick={(event) => {
                event.stopPropagation();
                onChange(selected.filter((value) => value.id !== item.id));
              }}
            >
              <X size={11} />
            </button>
          </span>
        ))}
        <input
          className={styles.pickerInput}
          role="combobox"
          aria-labelledby={`${id}-label`}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            open && options[active] ? `${id}-option-${active}` : undefined
          }
          value={query}
          disabled={disabled}
          placeholder={
            selected.length ? "继续输入关键字筛选并追加…" : placeholder
          }
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            onQueryChange(event.currentTarget.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />
        <ChevronDown
          size={14}
          aria-hidden="true"
          style={{ transform: open ? "rotate(180deg)" : undefined }}
        />
      </div>
      {open && !disabled && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownBar}>
            {sources ? (
              <div
                className={styles.sourceTabs}
                role="group"
                aria-label="基准来源筛选"
              >
                {sources.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={styles.sourceTab}
                    aria-pressed={source === item.value}
                    onClick={() => onSourceChange?.(item.value)}
                  >
                    {item.label}
                    {item.count !== undefined ? ` ${item.count}` : ""}
                  </button>
                ))}
              </div>
            ) : (
              <span role="status">
                {loading
                  ? "正在检索…"
                  : `匹配到 ${total ?? options.length} 条结果`}
              </span>
            )}
            <button
              type="button"
              className={styles.linkButton}
              onClick={selectAll}
              disabled={options.length === 0 || full}
            >
              全选当前筛选结果
            </button>
          </div>
          {error ? (
            <div className={styles.emptyOption} role="alert">
              {error}
            </div>
          ) : (
            <ul
              className={styles.options}
              id={listId}
              role="listbox"
              aria-multiselectable
            >
              {options.length === 0 && (
                <li className={styles.emptyOption} role="presentation">
                  {loading ? "正在检索…" : emptyText}
                </li>
              )}
              {options.map((option, index) => {
                const checked = selectedIds.has(option.id);
                return (
                  <li
                    key={option.id}
                    id={`${id}-option-${index}`}
                    role="option"
                    aria-selected={checked}
                    aria-disabled={!checked && full}
                    data-active={index === active}
                    className={styles.option}
                    onMouseEnter={() => setActive(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => toggle(option)}
                  >
                    <div className={styles.optionMain}>
                      <span className={styles.optionCheck} aria-hidden="true">
                        {checked ? (
                          <CheckSquare size={15} />
                        ) : (
                          <Square size={15} />
                        )}
                      </span>
                      <div className={styles.optionText}>
                        <div className={styles.optionTitle}>
                          <span className={styles.optionCode}>
                            {option.code}
                          </span>
                          <span className={styles.optionName}>
                            {option.name}
                          </span>
                        </div>
                        {(option.tags?.length || option.meta) && (
                          <div className={styles.optionMeta}>
                            {option.tags?.map((tag) => (
                              <span key={tag} className={styles.tag}>
                                {tag}
                              </span>
                            ))}
                            {option.meta && <span>{option.meta}</span>}
                          </div>
                        )}
                      </div>
                    </div>
                    {checked && (
                      <span className={styles.selectedMark}>已选择</span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {footer && <div className={styles.dropdownFooter}>{footer}</div>}
        </div>
      )}
    </div>
  );
};
