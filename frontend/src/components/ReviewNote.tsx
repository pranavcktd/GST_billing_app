/** Shown on return / JSON pages: the output is prepared from the user's entries and must be reviewed. */
export function ReviewNote() {
  return (
    <p className="mb-4 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
      Prepared from the entries in your books for your review. Please check the figures — ideally with your tax professional — and
      compare them with the GST portal before filing. Filing and payment are done by you on the GST portal.
    </p>
  );
}
