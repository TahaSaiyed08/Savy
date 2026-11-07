"use client";
import { InsetGroup, LargeTitle, Row, Status } from "@/components/ui";
import { api, withUser } from "@/lib/api";
import { useApi } from "@/lib/use-api";

// TODO(workstream 3): "+" opens a bottom sheet with the three intake paths (receipt, photo, type/hold-to-talk),
// each POSTing /intake/* then /items after the confirm step.
export default function MyList() {
  const { data, loading, error } = useApi(() => api.GET("/items", { params: withUser() }));
  return (
    <>
      <LargeTitle title="My List" />
      <Status loading={loading} error={error} empty={data?.length === 0 ? "Snap a receipt to fill your list." : undefined} />
      {!!data?.length && (
        <InsetGroup header={`${data.length} items`}>
          {data.map((i) => (
            <Row
              key={i.user_item_id}
              title={[i.brand, i.item, i.variant].filter(Boolean).join(" ")}
              subtitle={i.size_qty ? `${i.size_qty} ${i.size_unit}` : undefined}
              detail={i.source}
            />
          ))}
        </InsetGroup>
      )}
    </>
  );
}
